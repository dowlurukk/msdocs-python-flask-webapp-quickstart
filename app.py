import os
from reference.runinference2 import Inference
from flask import (Flask, redirect, render_template, request, jsonify,
                   send_from_directory, url_for)
from flask_cors import CORS

app = Flask(__name__)
# Configure CORS to allow the Static Web App origin (comma separate multiple origins in ALLOWED_ORIGINS)
allowed_origins = os.getenv(
   "ALLOWED_ORIGINS",
   "https://black-cliff-051a7af1e.4.azurestaticapps.net"
).split(",")
CORS(
   app,
   resources={r"/chat": {"origins": allowed_origins}},
   supports_credentials=True
)
vecstore_path =  '/home/filesharemount'
#vecstore_path =  '/Users/kirandowluru/testwebapp/msdocs-python-flask-webapp-quickstart/vectorstore'


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


@app.route('/chat', methods=['GET', 'POST', 'OPTIONS'])
def chat():
   # Handle CORS preflight quickly; headers are added by Flask-CORS
   if request.method == 'OPTIONS':
      return ('', 204)

   # Extract message across GET query, JSON body, or form-encoded
   message = None
   if request.method == 'GET':
      message = request.args.get('message')
   else:
      if request.is_json:
         body = request.get_json(silent=True) or {}
         message = body.get('message')
      if not message:
         # fallback to querystring or form
         message = request.args.get('message') or request.form.get('message')

   print(f'Request for medcopilot /chat received message={message}')

   try:
      inference = Inference(storeLocation=vecstore_path)
      response = inference.run_inference(message)
      print('Response from inference at the main api call:', response)
      response = serialize(response)
      return jsonify(response)
   except Exception as e:
      error = {"error": f"An error occurred. Please try again later.", "details": str(e)}
      return jsonify(error), 500

   
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
