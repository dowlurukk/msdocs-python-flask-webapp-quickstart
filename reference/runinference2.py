#from datetime import datetime
import sys
#import os
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

# LangChain 1.0 imports - use split packages and LCEL
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda


# --- Mock retriever for fallback ---
class MockRetriever:
    """Mock retriever for testing when vectorstore is not available"""
    def invoke(self, query):
        """LangChain 1.0 uses invoke instead of get_relevant_documents"""
        return [Document(page_content="This is a mock document for testing purposes.", metadata={})]
    
    def get_relevant_documents(self, query):
        """Backwards compatibility"""
        return self.invoke(query)


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
            print("✅ Chroma vectorstore initialized successfully.")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize vectorstore: {e}")
            print("Fallback: Using MockRetriever.")
            self.retriever = MockRetriever()

        # ✅ Initialize LLM (ChatOpenAI)
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY environment variable.")

            print("Initializing ChatOpenAI model...")
            self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
            print("✅ ChatOpenAI initialized successfully.")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize ChatOpenAI: {e}")
            self.llm = None

    # --- Main inference runner ---
    def run_inference(self, query, maintain_history=True):
        print(f"Running inference for query: {query}")
        self._initialize_components()

        try:
            results = self.query_reasoning(query, maintain_history)
        except Exception as e:
            print(f"❌ Error during inference: {e}")
            results = {
                "input": query,
                "context": [],
                "answer": "An internal error occurred while generating a response."
            }

        return results

    # --- Reasoning logic ---
    def query_reasoning(self, query, maintain_history=True):
        try:
            prompt_category = self.classify_prompt_category(query)[0]
            system_prompt = self.promt_categories.get_prompt(prompt_category)
            print(f"🧠 System prompt category: {prompt_category}")

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

            # Build LCEL RAG pipeline (LangChain 1.0 style)
            rag_chain = (
                {
                    "context": self.retriever | RunnableLambda(self._format_docs),
                    "input": RunnablePassthrough()
                }
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            # Invoke the chain with the query
            answer = rag_chain.invoke(query)
            
            # Get context documents separately for the response
            docs = self.retriever.invoke(query)
            
            results = {
                "input": query,
                "answer": answer,
                "context": docs
            }

            if maintain_history:
                self._update_conversation_history(query, answer)

        except Exception as e:
            print(f"❌ An error occurred in query_reasoning: {e}")
            results = {
                "input": query,
                "answer": "Sorry, I couldn't process your request.",
                "context": []
            }

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
        print("🧹 Conversation history cleared.")

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
    
    
    def generate_followup_questions(self, original_question, previous_results):
        followup_template = self.promt_categories.get_followup_template()
        
        try:
            # Create prompt template
            followup_prompt = PromptTemplate(
                input_variables=["original_question", "previous_answer", "context"],
                template=followup_template
            )
            
            # Build LCEL chain for followup questions (LangChain 1.0 style)
            followup_chain = followup_prompt | self.llm | StrOutputParser()
            
            # Get context from previous results
            context = previous_results.get("context", "No context available")
            previous_answer = previous_results.get("answer", "No answer available")
            
            # Invoke the chain
            text = followup_chain.invoke({
                "original_question": original_question,
                "previous_answer": previous_answer,
                "context": context
            })
            
            return (text or "").strip().split("\n")
            
        except Exception as e:
            print(f"Error generating followup questions: {e}")
            return ["Could not generate followup questions"]
 
    def classify_prompt_category(self, query):
        categories = self.promt_categories.get_categories()
        classification_template_text = self.promt_categories.get_classification_template()

        try:
            classify_prompt = PromptTemplate(
                input_variables=["query", "context"],
                template=classification_template_text,
            )
            
            # Build LCEL chain for classification (LangChain 1.0 style)
            classify_chain = classify_prompt | self.llm | StrOutputParser()
            
            text = classify_chain.invoke({
                "query": query,
                "context": "No context available"
            })
            return (text or "").strip().split("\n")
        except Exception as e:
            print(f"⚠️ Error classifying the query: {e}")
            return categories[0]


# --- Local test run ---
if __name__ == '__main__':
    inference = Inference()
    result = inference.run_inference("What is the treatment for hypertension?")
    print("Response:", result)
    print("✅ Inference completed successfully.")
