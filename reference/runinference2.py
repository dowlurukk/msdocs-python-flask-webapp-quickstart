from datetime import datetime
import sys
import os
from dotenv import load_dotenv
#import openai

# Load environment variables from .env file
load_dotenv()

# No longer need typing_extensions compatibility fix with Pydantic v1

# Only use pysqlite3 on Linux where it's available
if sys.platform == "linux":
    try:
        import pysqlite3
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    except ImportError:
        pass  # Fall back to built-in sqlite3

from reference.promptcategories import PromptCategories
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import HumanMessage, AIMessage, Document
from langchain.chains import LLMChain

class MockRetriever:
    """Mock retriever for testing when vectorstore is not available"""
    def get_relevant_documents(self, query):
        return [Document(page_content="This is a mock document for testing purposes.", metadata={})]

class Inference:
    def __init__(self, storeLocation = "vectorstore", max_history_messages=50):
        print(f"Initializing Inference with storeLocation: {storeLocation}")
        persist_directory = storeLocation
        
        # Use a simple approach for now - just create an empty retriever
        # In a real implementation, we'd load the vectorstore differently
        try:
            vectorstore = Chroma(collection_name="medcopilot", persist_directory=persist_directory, embedding_function=OpenAIEmbeddings())
            self.retriever = vectorstore.as_retriever()
            print(f"Vectorstore initialized with documents.")
        except Exception as e:
            print(f"Warning: Could not initialize vectorstore: {e}")
            print("Creating a mock retriever for testing...")
            # Create a mock retriever that returns empty results
            self.retriever = MockRetriever()
        
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

            # Get context documents
            docs = self.retriever.get_relevant_documents(query)
            context = self._format_docs(docs)
            
            # Create a simple chain for the old langchain version
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            # Get the answer using the chain
            answer = chain.run(context=context, input=query)
            
            results = {
                "answer": answer,
                "context": docs
            }
            
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
            
            # Create old-style chain
            followup_chain = LLMChain(llm=self.llm, prompt=followup_prompt)
            
            # Get context from previous results
            context = previous_results.get("context", "No context available")
            previous_answer = previous_results.get("answer", "No answer available")
            
            # Generate followup questions
            text = followup_chain.run(
                original_question=original_question,
                previous_answer=previous_answer,
                context=context
            )
            
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
            
            # Create old-style chain
            classify_chain = LLMChain(llm=self.llm, prompt=classify_prompt)
            
            text = classify_chain.run(
                query=query,
                context="No context available"
            )
            return (text or "").strip().split("\n")
            
        except Exception as e:   
            print(f"Error classifying the query: {e}")
            return categories[0]
    
if __name__ == '__main__':
    inference = Inference()
    response = inference.run_inference("What is the treatment for cancer?")
    print(response)
    print("Inference completed.")