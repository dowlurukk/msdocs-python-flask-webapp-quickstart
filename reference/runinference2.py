from datetime import datetime
#import openai
import pysqlite3
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
from .promptcategories import PromptCategories
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

class Inference:
    def __init__(self, storeLocation = "vectorstore"):
        print(f"Initializing Inference with storeLocation: {storeLocation}")
        persist_directory = storeLocation
        vectorstore = Chroma(collection_name="medcopilot", persist_directory=persist_directory, embedding_function=OpenAIEmbeddings())
        
        print(f"Vectorstore initialized with documents.")
        
        #TBD: Pass hints to the retriever to use the metadata for the search
        self.retriever = vectorstore.as_retriever()
        self.llm = ChatOpenAI(model="gpt-4o")
        self.rag_chains = {}
        self.promt_categories = PromptCategories()

    def run_inference(self, query):
        print(f"Running inference for query: {query}")
        results = self.query_reasoning(query)

        '''
        followup_questions = self.generate_followup_questions(query, results)
        print(f"FollowupQuestion : {followup_questions}")
        results["followup_questions"] = followup_questions
        print(f"Results with followup questions: {results}")
        '''
        return results

    def query_reasoning(self, query):
        try:
            prompt_category = self.classify_prompt_category(query)[0]
            system_prompt = self.promt_categories.get_prompt(prompt_category)
            print(f"System prompt: {system_prompt}")

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    ("human", "{input}"),
                ]
            )
            question_answer_chain = create_stuff_documents_chain(self.llm, prompt)
            rag_chain = create_retrieval_chain(self.retriever, question_answer_chain)
            results = rag_chain.invoke({"input": query})
        except Exception as e:
            print(f"An error occurred: {e}")
            results = {"context": "No context available", "answer": "Sorry, I couldn't process your request."}
        
        return results
    
    
    def generate_followup_questions(self, original_question, previous_results):
        followup_template = self.promt_categories.get_followup_template()
        
        try:
            # Create prompt template
            followup_prompt = PromptTemplate(
                input_variables=["original_question", "previous_answer", "context"],
                template=followup_template
            )
            
            # Create chain
            followup_chain = LLMChain(llm=self.llm, prompt=followup_prompt)
            
            # Get context from previous results
            context = previous_results.get("context", "No context available")
            previous_answer = previous_results.get("answer", "No answer available")
            
            # Generate followup questions
            followups = followup_chain.invoke({
                "original_question": original_question,
                "previous_answer": previous_answer,
                "context": context
            })
            
            return followups["text"].strip().split("\n")
            
        except Exception as e:
            print(f"Error generating followup questions: {e}")
            return ["Could not generate followup questions"]
 
    def classify_prompt_category(self, query):
        categories = self.promt_categories.get_categories()
        classify_template = self.promt_categories.get_classification_template()

        try:
            # Create prompt template
            classify_template = PromptTemplate(
                input_variables=["context"],
                template=classify_template
            )
            
            # Create chain
            rag_chain = LLMChain(llm=self.llm, prompt=classify_template)
            
            # Generate followup questions
            category = rag_chain.invoke({
                "query": query,
                "context": "No context available"
            })
            return category["text"].strip().split("\n")
            
        except Exception as e:   
            print(f"Error classifying the query: {e}")
            return categories[0]
    
if __name__ == '__main__':
    inference = Inference()
    response = inference.run_inference("What is the treatment for diabetes?")
    print(response)
    print("Inference completed.")