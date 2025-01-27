"""Implementation of a toolkit builder for the SymbolSearch API."""
from enum import Enum
from typing import List, Optional, Union

from automata.agent import (
    AgentToolkitBuilder,
    AgentToolkitNames,
    OpenAIAgentToolkitBuilder,
)
from automata.config.config_base import LLMProvider
from automata.config.prompt import AGENTIFIED_SEARCH_TEMPLATE
from automata.experimental.search import (
    ExactSearchResult,
    SourceCodeResult,
    SymbolRankResult,
    SymbolReferencesResult,
    SymbolSearch,
)
from automata.llm import (
    OpenAIChatCompletionProvider,
    OpenAIConversation,
    OpenAITool,
)
from automata.singletons.toolkit_registry import (
    OpenAIAutomataAgentToolkitRegistry,
)
from automata.tools import Tool, UnknownToolError


class SearchTool(Enum):
    """
    Available search tools.
    """

    AGENT_FACILITATED_SEARCH = "llm-facilitated-search"
    SYMBOL_SIMILARITY_SEARCH = "symbol-similarity-search"
    SYMBOL_RANK_SEARCH = "symbol-rank-search"
    SYMBOL_REFERENCES = "symbol-references"
    RETRIEVE_SOURCE_CODE_BY_SYMBOL = "retrieve-source-code-by-symbol"
    EXACT_SEARCH = "exact-search"


class SymbolSearchToolkitBuilder(AgentToolkitBuilder):
    """A class for interacting with the SymbolSearch API,
    which provides functionality to search an indexed python codebase."""

    def __init__(
        self,
        symbol_search: SymbolSearch,
        search_tools: Optional[List[SearchTool]] = None,
        top_n: int = 20,
        *args,
        **kwargs,
    ) -> None:
        self.symbol_search = symbol_search
        self.search_tools = search_tools or list(SearchTool)
        self.top_n = top_n

    def build_tool(self, tool_type: SearchTool) -> Tool:
        """Builds a suite of tools for searching the associated codebase."""
        tool_funcs = {
            SearchTool.AGENT_FACILITATED_SEARCH: self._symbol_agent_search_processor,
            SearchTool.SYMBOL_SIMILARITY_SEARCH: self._symbol_code_similarity_search_processor,
            SearchTool.SYMBOL_RANK_SEARCH: self._symbol_rank_search_processor,
            SearchTool.SYMBOL_REFERENCES: self._symbol_references_processor,
            SearchTool.RETRIEVE_SOURCE_CODE_BY_SYMBOL: self._retrieve_source_code_by_symbol_processor,
            SearchTool.EXACT_SEARCH: self._exact_search_processor,
        }
        tool_descriptions = {
            SearchTool.AGENT_FACILITATED_SEARCH: "Performs an agent facilitated similarity based search of symbols based on a given query string.",
            SearchTool.SYMBOL_SIMILARITY_SEARCH: "Performs a similarity based search of symbols based on a given query string.",
            SearchTool.SYMBOL_RANK_SEARCH: "Performs a ranked search of symbols based on a given query string.",
            SearchTool.SYMBOL_REFERENCES: "Finds all the references to a given symbol within the codebase.",
            SearchTool.RETRIEVE_SOURCE_CODE_BY_SYMBOL: "Returns the source code corresponding to a given symbol.",
            SearchTool.EXACT_SEARCH: "Performs an exact search for a given pattern across the codebase.",
        }
        if tool_type in tool_funcs:
            return Tool(
                name=tool_type.value,
                function=tool_funcs[tool_type],
                description=tool_descriptions[tool_type],
            )
        raise UnknownToolError(f"Invalid tool type: {tool_type}")

    def build(self) -> List[Tool]:
        return [self.build_tool(tool_type) for tool_type in self.search_tools]

    def process_query(
        self, tool_type: SearchTool, query: str
    ) -> Union[
        SymbolReferencesResult,
        SymbolRankResult,
        SourceCodeResult,
        ExactSearchResult,
    ]:
        """Processes a query by routing it to the appropriate sub-tool."""
        tools_dict = {tool.name: tool.function for tool in self.build()}
        return tools_dict[tool_type.value](query)

    # TODO - Cleanup these processors to ensure they behave well.
    # -- Right now these are just simplest implementations I can rattle off
    def _symbol_rank_search_processor(self, query: str) -> str:
        query_result = self.symbol_search.get_symbol_rank_results(query)
        return "\n".join(
            [symbol.dotpath for symbol, _rank in query_result][: self.top_n]
        )

    def _symbol_agent_search_processor(self, query: str) -> str:
        query_result = self.symbol_search.get_symbol_code_similarity_results(
            query
        )
        search_results = "\n".join(
            [symbol.dotpath for symbol, _similarity in query_result][
                : self.top_n
            ]
        )
        formatted_input_prompt = AGENTIFIED_SEARCH_TEMPLATE.format(
            SEARCH_RESULTS=search_results, QUERY=query
        )

        MODEL = "gpt-4"  # 3.5-turbo"
        TEMPERATURE = 0.7
        STREAM = True
        conversation = OpenAIConversation()

        completion_provider = OpenAIChatCompletionProvider(
            model=MODEL,
            temperature=TEMPERATURE,
            stream=STREAM,
            conversation=conversation,
            functions=[],
        )

        # Call a one-time completion with the provided context
        result = completion_provider.standalone_call(
            formatted_input_prompt
        ).strip()
        if result in search_results:
            return "\n".join(
                [result]
                + [symbol.dotpath for symbol, _similarity in query_result][
                    : self.top_n
                ]
            )
        else:
            return search_results

    def _symbol_code_similarity_search_processor(self, query: str) -> str:
        query_result = self.symbol_search.get_symbol_code_similarity_results(
            query
        )
        return "\n".join(
            [symbol.dotpath for symbol, _similarity in query_result][
                : self.top_n
            ]
        )

    def _symbol_references_processor(self, query: str) -> str:
        query_result = self.symbol_search.symbol_references(query)
        return "\n".join(
            [
                f"{symbol}:{str(reference)}"
                for symbol, reference in query_result.items()
            ][: self.top_n]
        )

    def _retrieve_source_code_by_symbol_processor(self, query: str) -> str:
        query_result = self.symbol_search.retrieve_source_code_by_symbol(query)
        return query_result or "No Result Found"

    def _exact_search_processor(self, query: str) -> str:
        query_result = self.symbol_search.exact_search(query)
        return "\n".join(
            [
                f"{symbol}:{str(references)}"
                for symbol, references in query_result.items()
            ][: self.top_n]
        )


@OpenAIAutomataAgentToolkitRegistry.register_tool_manager
class SymbolSearchOpenAIToolkitBuilder(
    SymbolSearchToolkitBuilder, OpenAIAgentToolkitBuilder
):
    TOOL_NAME = AgentToolkitNames.SYMBOL_SEARCH
    LLM_PROVIDER = LLMProvider.OPENAI

    def build_for_open_ai(self) -> List[OpenAITool]:
        tools = super().build()

        # Predefined properties and required parameters
        properties = {
            "query": {
                "type": "string",
                "description": "The query string to search for.",
            },
        }
        required = ["query"]

        openai_tools = []
        for tool in tools:
            openai_tool = OpenAITool(
                function=tool.function,
                name=tool.name,
                description=tool.description,
                properties=properties,
                required=required,
            )
            openai_tools.append(openai_tool)

        return openai_tools
