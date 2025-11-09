from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure SQLite compatibility (for Chroma on Linux)
if sys.platform == "linux":
    try:
        import pysqlite3
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    except ImportError:
        pass  # fallback to built-in sqlite3

# LangChain and project imports
from reference.promptcategories import PromptCategories
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, Document
from langchain.chains import LLMChain


# --- Mock retriever for fallback ---
class MockRetriever:
    """Used when vectorstore initialization fails."""
    def get_relevant_documents(self, query):
        print("Using mock retriever (no real vectorstore found).")
        return [Document(page_content="This is a mock document for testing purposes.", metadata={})]


# --- Inference Class ---
class Inference:
    def __init__(self, storeLocation="vectorstore", max_history_messages=50):
        print(f"Initializing Inference with storeLocation: {storeLocation}")
        self.storeLocation = storeLocation
        self.max_history_messages = max_history_messages
        self.conversation_history = []
        self.retriever = None
        self.llm = None
        self.promt_categories = PromptCategories()

    # --- Initialize Chroma and LLM lazily ---
    def _initialize_components(self):
        """Initialize components only when needed (lazy load)."""
        if self.retriever and self.llm:
            return  # Already initialized

        # ✅ Initialize Chroma
        try:
            if not os.path.exists(self.storeLocation):
                print(f"Creating missing vectorstore directory: {self.storeLocation}")
                os.makedirs(self.storeLocation, exist_ok=True)

            print("Initializing Chroma vectorstore...")
            vectorstore = Chroma(
                collection_name="medcopilot",
                persist_directory=self.storeLocation,
                embedding_function=OpenAIEmbeddings()
            )
            self.retriever = vectorstore.as_retriever()
            print("Chroma vectorstore initialized successfully.")
        except Exception as e:
            print(f"Warning: Could not initialize vectorstore: {e}")
            print("Using MockRetriever instead.")
            self.retriever = MockRetriever()

        # ✅ Initialize LLM (ChatOpenAI)
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY environment variable.")

            print("Initializing ChatOpenAI model...")
            self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
            print("ChatOpenAI initialized successfully.")
        except Exception as e:
            print(f"Warning: Could not initialize ChatOpenAI: {e}")
            self.llm = None

    # --- Main inference runner ---
    def run_inference(self, query, maintain_history=True):
        print(f"Running inference for query: {query}")
        self._initialize_components()

        try:
            results = self.query_reasoning(query, maintain_history)
        except Exception as e:
            print(f"Error during inference: {e}")
            results = {"context": "No context available", "answer": "An internal error occurred."}

        return results

    # --- Reasoning logic ---
    def query_reasoning(self, query, maintain_history=True):
        try:
            prompt_category = self.classify_prompt_category(query)[0]
            system_prompt = self.promt_categories.get_prompt(prompt_category)
            print(f"System prompt category: {prompt_category}")

            messages = [("system", system_prompt)]

            # Maintain conversation history
            if maintain_history and self.conversation_history:
                for msg in self.conversation_history:
                    if isinstance(msg, HumanMessage):
                        messages.append(("human", msg.content))
                    elif isinstance(msg, AIMessage):
                        messages.append(("ai", msg.content))

            messages.append(("human", "{input}"))

            # Add context if missing
            if "{context}" not in messages[0][1]:
                messages[0] = ("system", f"{messages[0][1]}\n\nContext:\n{{context}}")

            prompt = ChatPromptTemplate.from_messages(messages)

            # Retrieve docs from vectorstore
            docs = self.retriever.get_relevant_documents(query)
            context = self._format_docs(docs)

            # Build chain
            chain = LLMChain(llm=self.llm, prompt=prompt)
            answer = chain.run(context=context, input=query)

            results = {"answer": answer, "context": docs}

            if maintain_history:
                self._update_conversation_history(query, answer)

        except Exception as e:
            print(f"An error occurred in query_reasoning: {e}")
            results = {"answer": "Sorry, I couldn't process your request.", "context": []}

        return results

    # --- Utilities ---
    def _format_docs(self, docs):
        try:
            return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)
        except Exception:
            return str(docs)

    def _update_conversation_history(self, query, answer):
        self.conversation_history.append(HumanMessage(content=query))
        self.conversation_history.append(AIMessage(content=answer))
        if len(self.conversation_history) > self.max_history_messages:
            self.conversation_history = self.conversation_history[-self.max_history_messages:]

    def clear_history(self):
        self.conversation_history = []
        print("Conversation history cleared.")

    def get_history_summary(self):
        return {
            "message_count": len(self.conversation_history),
            "max_messages": self.max_history_messages,
            "history": [
                {
                    "role": "human" if isinstance(msg, HumanMessage) else "ai",
                    "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                }
                for msg in self.conversation_history
            ]
        }

    # --- Classification ---
    def classify_prompt_category(self, query):
        categories = self.promt_categories.get_categories()
        classification_template_text = self.promt_categories.get_classification_template()

        try:
            classify_prompt = PromptTemplate(
                input_variables=["query", "context"],
                template=classification_template_text,
            )
            classify_chain = LLMChain(llm=self.llm, prompt=classify_prompt)
            text = classify_chain.run(query=query, context="No context available")
            return (text or "").strip().split("\n")
        except Exception as e:
            print(f"Error classifying the query: {e}")
            return categories[0]


# --- Local test run ---
if __name__ == '__main__':
    inference = Inference()
    result = inference.run_inference("What is the treatment for hypertension?")
    print("Response:", result)
    print("Inference completed successfully.")
