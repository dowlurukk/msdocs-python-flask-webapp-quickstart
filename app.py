import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

app = Flask(__name__)
vecstore_path =  '/home/filesharemount'

@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/hello', methods=['POST'])
def hello():
   name = request.args.get('name')
   city = request.args.get('city')
   filenames = []
   for root, dirs, files in os.walk(vecstore_path):
       for file in files:
           print(file)
           filenames.append(file)

   return f'Hello, {name} from {city}, ! Welcome to the world of Flask! We have {len(filenames)} files in the filesharemount directory.'

   
if __name__ == '__main__':
   app.run()
