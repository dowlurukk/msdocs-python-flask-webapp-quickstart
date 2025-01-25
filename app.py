import os

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
   '''
   inference = Inference(storeLocation=vecstore_path)
   inference.create_rag_chains()
   response = inference.run_inference(message)
   print('Response from inference:', response)
   response = ResultParser(response).serialize()
   '''
   return jsonify("Canned response for message: " + message) 

if __name__ == '__main__':
   app.run()
