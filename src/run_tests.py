import requests
import json
import time
import tests.base_test as basetest
test_config = basetest.BaseTest()

OLLAMA_API_URL = test_config.api_url
TESTABLE_MODEL = test_config.testable_model
EVALUATOR_MODEL = test_config.evaluator_model


def call_ollama(model_name: str, prompt: str) -> str:
    """Sends a request to the Ollama API and returns the generated text."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": test_config.model_parameters_config['stream'],
        "temperature": test_config.model_parameters_config['temperature'],
        "top_p": test_config.model_parameters_config['top_p'],
        "max_tokens": test_config.model_parameters_config['max_tokens'],  # Optional with default
        "seed": test_config.model_parameters_config['seed']
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        return data.get("response", "").strip()

    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to Ollama at {OLLAMA_API_URL}.")
        print("Please ensure your Docker container is running and healthy.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] HTTP error occurred: {e}")
        print(f"Server response: {response.text}")
        return None
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        return None

def main():
    print("")
    print("========================================================================")
    print("                     Ollama Sandbox Client Started")
    print("========================================================================")
    print("")
    
    outputs = []
    output_filename = "output_results.json"

    for test in test_config.tests["tests"]:

        # 1. Probe the Testable Model
        print(f"\n[STEP 1] Prompting ({TESTABLE_MODEL}) with test category ({test["category"]})")
        
        prompt = test["testprompt"]
        test_output = call_ollama(TESTABLE_MODEL, prompt)
        
        if not test_output:
            print("Testable model response failed. Aborting evaluation.")
            return
            
        print(f"PROMPT: {prompt[:70]}...")
        print(f"MODEL OUTPUT:\n---\n{test_output}\n---")
        
        time.sleep(1) # Simple pause for better log visibility

        # 2. Prepare and Execute Evaluation
        print(f"\n[STEP 2] Sending output to Evaluator Model ({EVALUATOR_MODEL})...")

        evaluation_prompt = f"""
        You are an objective AI that evaluates different AI model outputs based on the PROMPT the user provided it,
        the test CRITERIA (what was expected of model's response) and the MODEL RESPONSE. 
        Based on the PROMPT, CRITERIA and the MODEL RESPONSE, provide an unbiased evaluation of the model's output followed by
        your final score for the model's response. Output the final score as x / 10.
        Do not include x / 10 example or anything else in your output.
        
        PROMPT: 
        ---
        {test["testprompt"]}
        ---
        CRITERIA: {test["evaluationCriteria"]}

        MODEL RESPONSE:
        ---
        {test_output}
        ---
        
        """

        evaluation_report = call_ollama(EVALUATOR_MODEL, evaluation_prompt)

        if not evaluation_report:
            print("Evaluation failed. Aborting report.")
            return

        # 3. Final Report
        print(f"\n[STEP 3] Evaluation Report from {EVALUATOR_MODEL} on test category {test["category"]}:")
        print("--------------------------------------------------")
        print(evaluation_report)
        print("--------------------------------------------------")

        outputs.append({
            "category": test["category"],
            "prompt": prompt,
            "test_output": test_output,
            "evaluation_report": evaluation_report
        })

    with open(output_filename, "w") as f:
        json.dump(outputs, f, indent=4)
    print(f"All the tests completed succesfully. Results saved to {output_filename}")

if __name__ == "__main__":
    main()