import json
import os
import asyncio

from google import genai


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not found")


client = genai.Client(api_key=API_KEY)

# IMPORTANT:
# This is ONLY the judge model.
# Your actual travel agent model in agent.py remains unchanged.
JUDGE_MODEL = "gemini-3.5-flash-lite"


# ---------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------

async def evaluate_response(test_case, actual_response):
    """
    Use an LLM to evaluate the agent's actual response
    against the expected behavior.
    """

    test_id = test_case["test_case"]
    user_input = test_case["input"]
    expected_behavior = test_case["expected_behavior"]

    judge_prompt = f"""
You are an expert evaluator judging a travel planning AI agent.

Your task is to evaluate the agent's ACTUAL RESPONSE against the
EXPECTED BEHAVIOR for the given USER INPUT.

Do not assume the agent is correct just because it produced a response.

Evaluate only what is actually present in the response.

USER INPUT:
{user_input}

EXPECTED BEHAVIOR:
{json.dumps(expected_behavior, indent=2, ensure_ascii=False)}

ACTUAL RESPONSE:
{actual_response}

Evaluate using these four metrics.

1. Correctness
- Did the response correctly understand and handle the user's request?
- Did it follow important constraints?
- Did it avoid incorrect behavior?

2. Relevance
- Is the response focused on the user's request?
- Does it avoid unrelated information?

3. Completeness
- Did it satisfy the important requirements listed in EXPECTED BEHAVIOR?
- Are important requested parts missing?

4. Tool Usage
- Judge whether the response demonstrates appropriate tool usage
  when tools are relevant.
- If no tool is required for the test case, give full credit.
- Do NOT penalize the agent merely because no tool was used when
  the task can reasonably be completed without tools.

Scoring:

1.0 = fully satisfies the criterion
0.75 = mostly satisfies it, with a minor issue
0.50 = partially satisfies it
0.25 = mostly fails it
0.0 = completely fails it

Then calculate:

overall_score =
(correctness + relevance + completeness + tool_usage) / 4

Status:
- PASS if overall_score >= 0.90
- PARTIAL if overall_score >= 0.50 and < 0.90
- FAIL if overall_score < 0.50

Give a short reason explaining the score.

IMPORTANT:
Return ONLY valid JSON.
Do not use markdown.
Do not add ```json.

Use exactly this structure:

{{
    "correctness": 1.0,
    "relevance": 1.0,
    "completeness": 1.0,
    "tool_usage": 1.0,
    "overall_score": 1.0,
    "overall_percentage": "100%",
    "status": "PASS",
    "reason": "Short explanation"
}}
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=JUDGE_MODEL,
            contents=judge_prompt,
        )

        text = response.text.strip()

        # Remove accidental markdown fences if model adds them
        if text.startswith("```json"):
            text = text[7:]

        if text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        evaluation = json.loads(text)

        # Recalculate score ourselves so the judge cannot
        # accidentally return an inconsistent overall score.
        correctness = float(evaluation["correctness"])
        relevance = float(evaluation["relevance"])
        completeness = float(evaluation["completeness"])
        tool_usage = float(evaluation["tool_usage"])

        overall_score = (
            correctness
            + relevance
            + completeness
            + tool_usage
        ) / 4

        if overall_score >= 0.90:
            status = "PASS"
        elif overall_score >= 0.50:
            status = "PARTIAL"
        else:
            status = "FAIL"

        return {
            "correctness": correctness,
            "relevance": relevance,
            "completeness": completeness,
            "tool_usage": tool_usage,
            "overall_score": round(overall_score, 2),
            "overall_percentage": f"{overall_score * 100:.0f}%",
            "status": status,
            "reason": evaluation.get("reason", "")
        }

    except Exception as e:

        return {
            "correctness": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
            "tool_usage": 0.0,
            "overall_score": 0.0,
            "overall_percentage": "0%",
            "status": "FAIL",
            "reason": f"LLM judge error: {str(e)}"
        }


# ---------------------------------------------------------
# Main Evaluation
# ---------------------------------------------------------

async def main():

    # Load test cases
    with open(
        "evaluation/eval_dataset.json",
        "r",
        encoding="utf-8"
    ) as file:
        test_cases = json.load(file)

    results = []

    for test in test_cases:

        print(f"\nRunning {test['test_case']}...")

        user_id = "evaluation_user"
        session_id = test["test_case"]

        response_text = ""

        try:

            # Import here so evaluator remains separate
            from google.adk.runners import InMemoryRunner
            from google.genai import types
            from agent import root_agent

            runner = InMemoryRunner(agent=root_agent)

            # Create session
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=session_id
            )

            user_message = types.Content(
                role="user",
                parts=[
                    types.Part(text=test["input"])
                ]
            )

            # Run actual agent
            events = runner.run(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            )

            for event in events:

                if event.is_final_response():

                    if event.content and event.content.parts:

                        parts = event.content.parts

                        text_parts = []

                        for part in parts:

                            if getattr(part, "text", None):
                                text_parts.append(part.text)

                        response_text = "\n".join(text_parts)

        except Exception as e:

            response_text = f"ERROR: {str(e)}"

        print("Agent response received.")

        # -------------------------------------------------
        # LLM-as-a-Judge
        # -------------------------------------------------

        print(f"Judging {test['test_case']}...")

        evaluation = await evaluate_response(
            test,
            response_text
        )

        print(
            f"Score: {evaluation['overall_percentage']} "
            f"| Status: {evaluation['status']}"
        )

        results.append({
            "test_case": test["test_case"],
            "input": test["input"],
            "expected_behavior": test["expected_behavior"],
            "actual_response": response_text,
            "evaluation": evaluation
        })

    # -----------------------------------------------------
    # Overall score
    # -----------------------------------------------------

    if results:

        overall_score = sum(
            result["evaluation"]["overall_score"]
            for result in results
        ) / len(results)

    else:

        overall_score = 0.0

    passed_cases = sum(
        1
        for result in results
        if result["evaluation"]["status"] == "PASS"
    )

    partial_cases = sum(
        1
        for result in results
        if result["evaluation"]["status"] == "PARTIAL"
    )

    failed_cases = sum(
        1
        for result in results
        if result["evaluation"]["status"] == "FAIL"
    )

    final_output = {
        "evaluation_summary": {
            "total_test_cases": len(results),
            "passed_cases": passed_cases,
            "partial_cases": partial_cases,
            "failed_cases": failed_cases,
            "overall_score": round(overall_score, 4),
            "overall_percentage": f"{overall_score * 100:.2f}%"
        },
        "test_results": results
    }

    # -----------------------------------------------------
    # Save results
    # -----------------------------------------------------

    os.makedirs(
        "evaluation",
        exist_ok=True
    )

    with open(
        "evaluation/evaluation_results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_output,
            file,
            indent=2,
            ensure_ascii=False
        )

    # -----------------------------------------------------
    # Console output
    # -----------------------------------------------------

    print("\n========================================")
    print("LLM EVALUATION COMPLETED")
    print("========================================")

    print(
        f"Overall Score: "
        f"{overall_score * 100:.2f}%"
    )

    print(
        f"Passed Cases: "
        f"{passed_cases}/{len(results)}"
    )

    print(
        f"Partial Cases: "
        f"{partial_cases}/{len(results)}"
    )

    print(
        f"Failed Cases: "
        f"{failed_cases}/{len(results)}"
    )

    print(
        "Results saved to "
        "evaluation/evaluation_results.json"
    )


if __name__ == "__main__":
    asyncio.run(main())