import os
import traceback
from reference.runinference2 import Inference
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Configure CORS to allow specific origins (adjust as needed)
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://black-cliff-051a7af1e.4.azurestaticapps.net"
).split(",")

CORS(
    app,
    resources={r"/chat": {"origins": allowed_origins}},
    supports_credentials=True
)

# Path to your vector store
vecstore_path = '/home/filesharemount'
# Example for local testing:
# vecstore_path = '/Users/kirandowluru/testwebapp/msdocs-python-flask-webapp-quickstart/vectorstore'


@app.route('/')
def mainPage():
    """Root route - returns a simple greeting message."""
    name = request.args.get('name')
    city = request.args.get('city')

    filenames = []
    for root, dirs, files in os.walk(vecstore_path):
        for file in files:
            print(file)
            filenames.append(file)

    return f"Hello there! Welcome to the Medcopilot, the medical guidelines assistant!"


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Main chat route for MedCopilot."""
    # Handle preflight request (CORS)
    if request.method == 'OPTIONS':
        return ('', 204)

    # Validate request body
    if not request.is_json:
        return jsonify({"error": "Invalid request. Expected application/json body."}), 400

    body = request.get_json(silent=True) or {}
    message = body.get('message')

    if not message:
        return jsonify({"error": "Missing 'message' in JSON body."}), 400

    print(f"📩 Received message: {message}")

    try:
        # Create an inference object and get a response
        inference = Inference(storeLocation=vecstore_path)
        response = inference.run_inference(message)

        print(f"✅ Raw inference response: {response}")

        # Serialize and return
        response = serialize(response)
        print(f"✅ Serialized response: {response}")
        return jsonify(response)

    except Exception as e:
        print("🔥 Error in /chat route:")
        traceback.print_exc()  # Shows the error details in Cloud Run logs
        error = {
            "error": "An error occurred. Please try again later.",
            "details": str(e)
        }
        return jsonify(error), 500


def serialize(lang_chain_result):
    """Convert inference results safely into JSON format."""
    # If inference output is not a dictionary (unexpected case)
    if not isinstance(lang_chain_result, dict):
        return {
            "input": None,
            "answer": str(lang_chain_result),
            "context": []
        }

    # Safely extract fields with defaults
    input_text = lang_chain_result.get("input", "")
    answer_text = lang_chain_result.get("answer", "")
    context_items = lang_chain_result.get("context", [])

    context_list = []
    for item in context_items:
        try:
            context_dict = {
                "metadata": getattr(item, "metadata", {}),
                "page_content": getattr(item, "page_content", "")
            }
            context_list.append(context_dict)
        except Exception as e:
            print(f"⚠️ Skipped invalid context item: {e}")

    return {
        "input": input_text,
        "answer": answer_text,
        "context": context_list
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
