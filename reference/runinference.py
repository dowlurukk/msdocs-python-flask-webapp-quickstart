#using langchain_community 
#import tkinter as tk
#from tkinter import scrolledtext
from datetime import datetime
#import openai
import pysqlite3
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import PyPDFDirectoryLoader

from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import AzureBlobStorageContainerLoader
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import getpass
import os

from transformers import pipeline
from langchain.callbacks import get_openai_callback


# Define the categories
categories = [
    "Diagnosis and Differential Diagnosis",
    "Treatment Recommendations",
    "Drug Information",
    "Patient Education and Counseling",
    "Medical News and Research",
    "Prevention and Screening",
]

template_gen_prompt = (
            "You are an expert at generating prompt templates for Language Models."
            "Generate a system prompt template relavant to this question that will guide the model to reason the question only based on the context provided."
            "The prompt should guide the model to format the answer with the relevant headings and subheadings, text highlighting and references." 
            "The generated template should always start and end with 3 dashes"
            "The generated template should also have the following sections Recommendation, Detailed explanation, Supportive Arguments, Important Considerations, Recommendations from other guidelines, Controversies in management, Primary source of data"
            "{context}"
)

system_prompt = (
            "You are an expert assistant guiding a physician in providing guideline based recommendations for patient care. Take the most recent guideline data as primary source and use any other guidelines papers that were published within 2years of the primary source for comparison. If there is no relevant guideline data in the last 2years, use older data, but explicitly mention that there are no recent guidelines on the topic.  "
            "Use the following pieces of retrieved context to answer the question in the following format: "
            "\n\n (Recommendation:)"
            "    * [Provide a clear and concise recommendation along with context like what data and guidelines the recommendation is taken from]"
            "\n\n (Rationale and Supportive Arguments:)"
            "\n    * [Provide a detailed explanation of the recommendation along with the rationale for the recommendation with context such as what are the main pathophysiological considerations for the question in context, data behind management strategy and guidelines the recommendation is taken from]"
            "\n    * [Detail the Reasoning behind the recommendation, rationale for the recommendation with pathophysiological context from the guidelines as well as the references contained within the guidelines and detail the risk of harm without the recommended management strategy]" 
            "\n    * [List of factors and links supporting the recommendation] "
            "\n\n (Important Considerations:)"
            "\n    * [List of key factors to consider along with links to the references]"
            "\n    * [List any key factors that might make this recommendation unsuitable for a particular patient]"
            "\n    * [List any key risks, complications or harm that could occur with the recommendation]" 
            "\n    * [List any alternative management strategies ]"  
            "\n\n (Relevant guidelines:)"
            "\n    * [Mention the main guidelines used to formulate the above recommendation. If multiple guidelines were used to synthesis the above recommendations, mention all with title of guidelines and year of publication and links for references]"
            "\n    * [If there is difference in opinion between different guidelines, Summarize and highlight the differences in guidelines other than the main guideline used for the recommendation]" 
            "\n    * [Summarize and highlight if there is a different recommendation from different regional or older guidelines]"       
            "[Optional: Add specific details or constraints to guide the answer]"
            "\n\n (Areas of uncertainty and Controversies in management)"
            "\n   * [List any opposing schools of thought, and any differences in recommendation in other  recent guidelines  within 4 years of the primary guideline. Explain any controversies on the topic ]"
            "\n (Primary source of data: )"
            "\n   * [ list the Titles of the guidelines used for this recommendation]"
            "\n Year of publication: "
            "\n   * [ show the year of guideline used for recommendation along with society of the guideline]"
            "\n If there is not enough guideline supported data to make a recommendation, please explain that."
            "\n If you don't know the answer, say that you don't know. "
            "\n\n"
            "{context}"
        )

patient_prompt = (
            "You are an expert assistant guiding a patient question-answering tasks. Take the most recent guideline data as primary source and use any other guidelines that were published within few years of the primary source for comparison. If there is no relevant guideline data in the last 2years, use older data, but explicitly mention that there are no recent guidelines on the topic.  "
            "Use the following pieces of retrieved context to answer the question in the following format: "
            "\n\n (Recommendation:)"
            "    * [Provide a clear and concise recommendation along with context like what data and guidelines the recommendation is taken from]"
            "\n\n (Detailed explanation:)"
            "\n    * [Provide a detailed explanation of the recommendation along with the rationale for the recommendation with context like what data and guidelines the recommendation is taken from]"
            "\n\n (Supportive Arguments:)"
            "\n    * [List of factors and links supporting the recommendation] "
            "\n    * [Detail the Reasoning behind the recommendation, rationale for the recommendation with pathophysiological context from the guidelines as well as the references contained within the guidelines and detail the risk of harm without the recommended management strategy]" 
            "\n\n (Important Considerations:)"
            "\n    * [List of key factors to consider along with links to the references]"
            "\n    * [List any key factors that might make this recommendation unsuitable for a particular patient]"
            "\n    * [List any key risks, complications or harm that could occur with the recommendation]" 
            "\n    * [List any alternative management strategies ]"  
            "\n\n (Recommendations from other guidelines:)"
            "\n    * [Summarize recommendation from other guidelines when available, along with title of guidelines and year of publication and links for references]" 
            "\n    * [Summarize and highlight if there is a different recommendation from different regional or older guidelines]"       
            "[Optional: Add specific details or constraints to guide the answer]"
            "\n\n (Controversies in management)"
            "\n   * [List any opposing schools of thought, and any differences in recommendation in other  recent guidelines  within 4 years of the primary guideline. Explain any controversies on the topic ]"
            "\n (Primary source of data: )"
            "\n   * [ list the Titles of the guidelines used for this recommendation]"
            "\n Year of publication: "
            "\n   * [ show the year of guideline used for recommendation along with society of the guideline]"
            "If you don't know the answer, say that you don't know. "
            "\n\n"
            "{context}"
        )

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


    def run_inference(self, message):
        try:
            response = self.query_reasoning(message)
            return response
        except Exception as e:
            print(f"Error processing request: {e}")
            return f"An error occurred. Please try again later."

    '''
    Query function to retrieve from the chain... 
    '''
    def query_reasoning(self, question):

        '''
        # this is the code for streaming... 
        def stream_response(callback):
            for chunk in callback:
                if chunk.get("choices"):
                    yield chunk["choices"][0]["delta"].get("content", "")

        try:
            prompt_template_main = system_prompt 
            main_rag_chain = self.create_chain_rag(prompt_template_main)
            with get_openai_callback() as callback:
                main_rag_chain.invoke({"input": question}, callback=callback)
                response_stream = stream_response(callback)
                for chunk in response_stream:
                    print(chunk, end='', flush=True)
        except Exception as e:
            print(f"An error occurred: {e}")
            return "An error occurred. Please try again later."
        '''

        # TBD -> get the category from the question
        
        #category = self.classify_query(question)
        #rag_chain = self.rag_chains[category]
        
        #rag_chain_template = self.rag_chains["generate_template"]
        '''
        try:
            prompt_template_rag =  self.create_chain_rag(system_prompt)
            prompt_template = prompt_template_rag.invoke({"input": question})
        except Exception as e:
            print(f"An error occurred: {e}")
            results = {"context": "No context available", "answer": "Sorry, I couldn't process your request."}

        #print(prompt_template)
        #print("-----------------")
        #Extract the template from the "answer" key of the dictionary
        for key, value in prompt_template.items():
            if(key == "answer"):
                start = value.index('---') + 3
                template = value[start:].strip()
                print(f"{template}")
        #print(results["context"][0].page_content)
        #print(results["context"][0].metadata)
        '''

        try:
            prompt_template_main = system_prompt 
            main_rag_chain = self.create_chain_rag(prompt_template_main)
            results = main_rag_chain.invoke({"input": question})
        except Exception as e:
            print(f"An error occurred: {e}")
            results = {"context": "No context available", "answer": "Sorry, I couldn't process your request."}
        
        #print(results)
        #print(results["context"][0].page_content)
        #print(results["context"][0].metadata)
        followup_questions = self.generate_followup_questions(question, results)
        print(f"FollowupQuestion : {followup_questions}")
        results["followup_questions"] = followup_questions
        print(f"Results with followup questions: {results}")

        return results
        
    
    def generate_followup_questions(self, original_question, previous_results):
    
        followup_template = """
        Based on the original question: {original_question}
        And the previous answer: {previous_answer}
        With context: {context}
        
        Generate 3 most relevant followup questions that would help explore this topic of the question further.
        You must return valid JSON for the three related questions, without any additional text:
        {
          "question": "first related question",
          "question": "second related question",
          "question": "third related question",
        },
        Make your JSON output concise and valid.
        """
        
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

    '''
    Classify the given query into a category
    '''
    def classify_query(self, query):
        ''' 
        # Load a pre-trained model and tokenizer
        classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        # Use the classifier to predict the category
        result = classifier(query, candidate_labels=categories)
        # Get the category with the highest score
        category = result['labels'][0]
        '''
        return "Diagnosis and Differential Diagnosis"

    '''
    Create a RAG chain 
    '''
    def create_chain_rag(self, system_prompt=None):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        question_answer_chain = create_stuff_documents_chain(self.llm, prompt)
        rag_chain = create_retrieval_chain(self.retriever, question_answer_chain)

        return rag_chain
    
    '''
    def create_rag_chains(self):
        for category in categories:
            self.rag_chains[category] = self.create_chain_rag(category)
    '''

if __name__ == "__main__":
    inference = Inference()
    #nference.create_rag_chains()
    answer = inference.query_reasoning("What is the best modality to screen for Barrett’s esophagus? What should be the recommendation if a screening endoscopy for Barrett’s esophagus, shows no evidence of Barrett’s esophagus?")
    print(answer)