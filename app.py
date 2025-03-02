import os
from reference.runinference import Inference
from flask import (Flask, redirect, render_template, request,jsonify,
                   send_from_directory, url_for)

app = Flask(__name__)
vecstore_path =  '/home/filesharemount'

@app.route('/')
def mainPage():
   name = request.args.get('name')
   city = request.args.get('city')
   filenames = []
   for root, dirs, files in os.walk(vecstore_path):
       for file in files:
           print(file)
           filenames.append(file)

   return f'Hello there, ! Welcome to the Medcopilot, the medical guidelines assistant! '


@app.route('/chat', methods=['POST'])
def chat():
   message = request.args.get('message')
   print(f'Request for medcopilot /chat received message={message}')
   try:
      inference = Inference(storeLocation=vecstore_path)
      #inference.create_rag_chains()
      response = inference.run_inference(message)
      print('Response from inference at the main api call:', response)
      response = serialize(response)
   except Exception as e:
      response = f"An error occurred. Please try again later. Error: {e}"

   return jsonify(response)

   
def serialize(lang_chain_result): 
   context_list = []

   for item in lang_chain_result['context']:
      context_dict = {}
      context_dict['metadata'] = item.metadata 
      context_dict['page_content'] = item.page_content
      context_list.append(context_dict)

   
   return {"input": lang_chain_result['input'],
            "answer": lang_chain_result['answer'],
            "context": context_list}

if __name__ == '__main__':
   app.run()
