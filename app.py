import os
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from reference.runinference2 import Inference

app = Flask(__name__)

# Configure CORS to allow frontend access (adjust this if needed)
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://black-cliff-051a7af1e.4.azurestaticapps.net"
).split(",")
CORS(
    app,
    resources={r"/chat": {"origins": allowed_origins}},
    supports_credentials=True
)

# Path to vector store
vecstore_path = '/home/filesharemount'


@app.route('/')
def main_page():
    """Basic welcome route"""
    return 'Hello there! Welcome to MedCopilot — your medical guidelines assistant!'


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Main API endpoint to handle chat messages"""
    if request.method == 'OPTIONS':
        return ('', 204)

    if not request.is_json:
        return jsonify({"error": "Invalid request. Expected JSON body."}), 400

    body = request.get_json(silent=True) or {}
    message = body.get('message')

    if not message:
        return jsonify({"error": "Missing 'message' in JSON body."}), 400

    print(f"📩 Received message: {message}")

    try:
        inference = Inference(storeLocation=vecstore_path)
        response = inference.run_inference(message)
        print("✅ DEBUG: Raw response from Inference:", response)

        serialized = serialize(response)
        print("✅ DEBUG: Serialized response:", serialized)

        return jsonify(serialized)

    except Exception as e:
        print("❌ ERROR in /chat handler:")
        print(traceback.format_exc())

        error = {
            "error": "An error occurred while processing your request.",
            "details": str(e)
        }
        return jsonify(error), 500


def serialize(result):
    """
    Safely convert inference output into a JSON serializable dict.
    Handles cases where output might not contain expected fields.
    """
    try:
        # If the result is already a dict with the expected keys
        if isinstance(result, dict):
            input_text = result.get('input', "")
            answer = result.get('answer', str(result))
            context_items = result.get('context', [])

            context_list = []
            for item in context_items:
                # Handle structured context items gracefully
                context_dict = {
                    "metadata": getattr(item, "metadata", {}),
                    "page_content": getattr(item, "page_content", str(item))
                }
                context_list.append(context_dict)

            return {
                "input": input_text,
                "answer": answer,
                "context": context_list
            }

        # If result is just a string (LLM answer)
        elif isinstance(result, str):
            return {"input": "", "answer": result, "context": []}

        # Unknown type
        else:
            return {
                "input": "",
                "answer": str(result),
                "context": []
            }

    except Exception as e:
        print("⚠️ Error during serialization:", e)
        return {
            "input": "",
            "answer": "An internal error occurred during serialization.",
            "context": []
        }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
