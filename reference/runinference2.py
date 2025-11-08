from datetime import datetime
import sys
import os
from dotenv import load_dotenv
#import openai

# Load environment variables from .env file
load_dotenv()

# Azure App Service compatibility fix for typing_extensions
def fix_azure_typing_extensions():
    """Fix typing_extensions import conflicts in Azure App Service"""
    try:
        # Check if we're in Azure environment
        if "/tmp/" in os.environ.get('PYTHONPATH', '') or any('/tmp/' in p for p in sys.path):
            # Try to fix the module path issue
            target_dir = "/home/site/wwwroot/deps"
            os.makedirs(target_dir, exist_ok=True)
            
            import subprocess
            # Install typing_extensions to a local directory
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "--force-reinstall", "--target", target_dir,
                "typing_extensions==4.15.0"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Insert at the beginning of sys.path
            if target_dir not in sys.path:
                sys.path.insert(0, target_dir)
                
            # Clear any cached imports
            if 'typing_extensions' in sys.modules:
                del sys.modules['typing_extensions']
            if 'pydantic_core' in sys.modules:
                del sys.modules['pydantic_core']
            if 'pydantic' in sys.modules:
                del sys.modules['pydantic']
                
    except Exception as e:
        print(f"Warning: Could not fix typing_extensions: {e}")
        pass

# Apply the fix for Azure App Service
fix_azure_typing_extensions()

# Only use pysqlite3 on Linux where it's available
if sys.platform == "linux":
    try:
        import pysqlite3
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    except ImportError:
        pass  # Fall back to built-in sqlite3

from .promptcategories import PromptCategories
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnableParallel,
    RunnablePassthrough,
    RunnableLambda,
)

class Inference:
    def __init__(self, storeLocation = "vectorstore", max_history_messages=50):
        print(f"Initializing Inference with storeLocation: {storeLocation}")
        persist_directory = storeLocation
        vectorstore = Chroma(collection_name="medcopilot", persist_directory=persist_directory, embedding_function=OpenAIEmbeddings())
        
        print(f"Vectorstore initialized with documents.")
        
        #TBD: Pass hints to the retriever to use the metadata for the search
        self.retriever = vectorstore.as_retriever()
        self.llm = ChatOpenAI(model="gpt-4o")
        self.rag_chains = {}
        self.promt_categories = PromptCategories()
        
        # Initialize conversation history
        self.conversation_history = []
        self.max_history_messages = max_history_messages

    def _format_docs(self, docs):
        """Join retrieved documents' page_content for prompt context."""
        try:
            return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)
        except Exception:
            # Fallback to string if docs isn't iterable
            return str(docs)

    def run_inference(self, query, maintain_history=True):
        print(f"Running inference for query: {query}")
        results = self.query_reasoning(query, maintain_history)

        '''
        followup_questions = self.generate_followup_questions(query, results)
        print(f"FollowupQuestion : {followup_questions}")
        results["followup_questions"] = followup_questions
        print(f"Results with followup questions: {results}")
        '''
        return results

    def query_reasoning(self, query, maintain_history=True):
        try:
            prompt_category = self.classify_prompt_category(query)[0]
            system_prompt = self.promt_categories.get_prompt(prompt_category)
            print(f"System prompt: {system_prompt}")

            # Build messages with conversation history
            messages = [("system", system_prompt)]
            
            # Add conversation history if available
            if maintain_history and self.conversation_history:
                for msg in self.conversation_history:
                    if isinstance(msg, HumanMessage):
                        messages.append(("human", msg.content))
                    elif isinstance(msg, AIMessage):
                        messages.append(("ai", msg.content))
            
            # Add current query
            messages.append(("human", "{input}"))
            
            # Ensure the system message includes a {context} slot for retrieved docs
            # If not already included, extend it here
            if "{context}" not in messages[0][1]:
                messages[0] = ("system", f"{messages[0][1]}\n\nContext:\n{{context}}")

            prompt = ChatPromptTemplate.from_messages(messages)

            # Build LCEL RAG pipeline
            parser = StrOutputParser()
            answer_chain = (
                {
                    "context": self.retriever | RunnableLambda(self._format_docs),
                    "input": RunnablePassthrough(),
                }
                | prompt
                | self.llm
                | parser
            )

            # Return both the model answer and raw documents for existing serializer
            rag_chain = RunnableParallel(
                answer=answer_chain,
                context=self.retriever,
            )
            results = rag_chain.invoke(query)
            
            # Update conversation history
            if maintain_history:
                self._update_conversation_history(query, results.get("answer", ""))
                
        except Exception as e:
            print(f"An error occurred: {e}")
            results = {"context": "No context available", "answer": "Sorry, I couldn't process your request."}
        
        return results
    
    def _update_conversation_history(self, query, answer):
        """Update conversation history with the latest exchange"""
        self.conversation_history.append(HumanMessage(content=query))
        self.conversation_history.append(AIMessage(content=answer))
        
        # Trim history to maintain context window
        # Keep only the last N messages (N = max_history_messages)
        if len(self.conversation_history) > self.max_history_messages:
            self.conversation_history = self.conversation_history[-self.max_history_messages:]
    
    def clear_history(self):
        """Clear the conversation history"""
        self.conversation_history = []
        print("Conversation history cleared.")
    
    def get_history_summary(self):
        """Get a summary of the current conversation history"""
        return {
            "message_count": len(self.conversation_history),
            "max_messages": self.max_history_messages,
            "history": [
                {"role": "human" if isinstance(msg, HumanMessage) else "ai", 
                 "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content}
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
            
            # Create LCEL chain
            followup_chain = followup_prompt | self.llm | StrOutputParser()
            
            # Get context from previous results
            context = previous_results.get("context", "No context available")
            previous_answer = previous_results.get("answer", "No answer available")
            
            # Generate followup questions
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
            # Create prompt template
            classify_prompt = PromptTemplate(
                input_variables=["query", "context"],
                template=classification_template_text,
            )
            
            # Create LCEL chain
            classify_chain = classify_prompt | self.llm | StrOutputParser()
            
            text = classify_chain.invoke({
                "query": query,
                "context": "No context available",
            })
            return (text or "").strip().split("\n")
            
        except Exception as e:   
            print(f"Error classifying the query: {e}")
            return categories[0]
    
if __name__ == '__main__':
    inference = Inference()
    response = inference.run_inference("What is the treatment for cancer?")
    print(response)
    print("Inference completed.")