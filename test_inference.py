"""
Local test script for runinference2.py

Tests basic inference functionality, conversation history,
prompt classification, and error handling.

Usage:
    python test_inference.py
    python test_inference.py --vectorstore ./vectorstore
"""

import argparse
import json
import time
import sys
from pathlib import Path

# Add the project root to path so we can import reference module
sys.path.insert(0, str(Path(__file__).parent))

from reference.runinference2 import Inference


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def test_basic_query(inference):
    """Test basic query functionality"""
    print_section("TEST 1: Basic Query")
    
    query = "What are the symptoms of diabetes?"
    print(f"Query: {query}\n")
    
    start = time.time()
    response = inference.run_inference(query)
    elapsed = time.time() - start
    
    print(f"Answer: {response.get('answer', 'No answer')[:200]}...")
    print(f"\nContext documents: {len(response.get('context', []))}")
    print(f"Response time: {elapsed:.2f}s")
    
    return response


def test_conversation_history(inference):
    """Test conversation history tracking"""
    print_section("TEST 2: Conversation History")
    
    # Clear any existing history
    inference.clear_history()
    
    # First query
    q1 = "What is hypertension?"
    print(f"Query 1: {q1}")
    r1 = inference.run_inference(q1)
    print(f"Answer 1: {r1.get('answer', 'No answer')[:150]}...\n")
    
    # Follow-up query (should use context from previous)
    q2 = "What are the treatment options?"
    print(f"Query 2 (follow-up): {q2}")
    r2 = inference.run_inference(q2)
    print(f"Answer 2: {r2.get('answer', 'No answer')[:150]}...\n")
    
    # Check history
    history = inference.get_history_summary()
    print(f"Conversation history: {history['message_count']} messages")
    print(f"(Max: {history['max_messages']})\n")
    
    # Display history summary
    for i, msg in enumerate(history['history'], 1):
        role = msg['role'].upper()
        content = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
        print(f"  {i}. [{role}] {content}")
    
    return history


def test_classification(inference):
    """Test prompt classification"""
    print_section("TEST 3: Prompt Classification")
    
    test_queries = [
        "What is the treatment for diabetes?",
        "Explain the pathophysiology of heart failure",
        "What are the guidelines for hypertension management?",
        "Tell me about COVID-19 symptoms"
    ]
    
    for query in test_queries:
        category = inference.classify_prompt_category(query)
        print(f"Query: {query}")
        print(f"Category: {category[0] if category else 'Unknown'}\n")


def test_history_management(inference):
    """Test history clearing and limits"""
    print_section("TEST 4: History Management")
    
    # Create a new inference with small history limit
    small_inference = Inference(max_history_messages=4)
    
    print("Creating conversation with max 4 messages...")
    queries = [
        "What is diabetes?",
        "What are the symptoms?",
        "How is it diagnosed?",
        "What are the treatments?"
    ]
    
    for i, q in enumerate(queries, 1):
        small_inference.run_inference(q)
        summary = small_inference.get_history_summary()
        print(f"After query {i}: {summary['message_count']} messages in history")
    
    # Check that history was trimmed
    final_summary = small_inference.get_history_summary()
    print(f"\nFinal history count: {final_summary['message_count']}")
    print(f"Expected (trimmed to max): {small_inference.max_history_messages}")
    
    # Clear history
    print("\nClearing history...")
    small_inference.clear_history()
    cleared_summary = small_inference.get_history_summary()
    print(f"After clear: {cleared_summary['message_count']} messages")


def test_no_history_mode(inference):
    """Test queries without maintaining history"""
    print_section("TEST 5: No History Mode")
    
    inference.clear_history()
    
    print("Query 1 (with history):")
    q1 = "What is hypertension?"
    inference.run_inference(q1, maintain_history=True)
    print(f"  {q1}")
    print(f"  History count: {inference.get_history_summary()['message_count']}")
    
    print("\nQuery 2 (without history):")
    q2 = "What is diabetes?"
    inference.run_inference(q2, maintain_history=False)
    print(f"  {q2}")
    print(f"  History count: {inference.get_history_summary()['message_count']}")
    print("  (Should still be 2 - only first query was saved)")


def test_error_handling():
    """Test error handling with invalid vectorstore"""
    print_section("TEST 6: Error Handling")
    
    try:
        print("Attempting to create inference with non-existent vectorstore...")
        # This should either fail gracefully or use MockRetriever
        bad_inference = Inference(storeLocation="./nonexistent_vectorstore")
        
        print("✓ Inference created (likely using MockRetriever)")
        
        response = bad_inference.run_inference("Test query")
        print(f"Response: {response.get('answer', 'No answer')[:100]}...")
        
    except Exception as e:
        print(f"✗ Error occurred (expected): {type(e).__name__}: {e}")


def run_all_tests(vectorstore_path="vectorstore"):
    """Run all test suites"""
    print("\n" + "🧪" * 30)
    print("  INFERENCE MODULE TEST SUITE")
    print("🧪" * 30)
    print(f"\nVectorstore location: {vectorstore_path}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Initialize inference
        print("\nInitializing Inference module...")
        inference = Inference(storeLocation=vectorstore_path, max_history_messages=50)
        print("✓ Inference initialized successfully\n")
        
        # Run tests
        test_basic_query(inference)
        test_conversation_history(inference)
        test_classification(inference)
        test_history_management(inference)
        test_no_history_mode(inference)
        test_error_handling()
        
        print_section("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        
    except Exception as e:
        print_section("❌ TEST SUITE FAILED")
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Test the Inference module locally"
    )
    parser.add_argument(
        "--vectorstore",
        default="vectorstore",
        help="Path to vectorstore directory (default: vectorstore)"
    )
    parser.add_argument(
        "--test",
        choices=["basic", "history", "classification", "management", "no-history", "errors", "all"],
        default="all",
        help="Specific test to run (default: all)"
    )
    
    args = parser.parse_args()
    
    if args.test == "all":
        run_all_tests(args.vectorstore)
    else:
        # Run specific test
        inference = Inference(storeLocation=args.vectorstore)
        
        test_map = {
            "basic": test_basic_query,
            "history": test_conversation_history,
            "classification": test_classification,
            "management": test_history_management,
            "no-history": test_no_history_mode,
            "errors": test_error_handling
        }
        
        test_fn = test_map.get(args.test)
        if test_fn:
            if args.test == "errors":
                test_fn()  # Error test doesn't need inference parameter
            else:
                test_fn(inference)
            print_section("✅ TEST COMPLETED")


if __name__ == "__main__":
    main()
