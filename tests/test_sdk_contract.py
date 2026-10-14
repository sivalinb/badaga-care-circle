"""Exercise the actual OpenAI SDK and Pydantic parser using an in-memory HTTP transport."""
from dataclasses import replace
from types import SimpleNamespace
import json
import httpx
from openai import OpenAI
from badaga_care.models import Actor
from badaga_care.providers import OpenAIProvider
from badaga_care.service import CareService


def test_real_sdk_request_and_structured_response_contract(settings,monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","unit-test-placeholder")
    configured = replace(settings,model="test-model")
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append((request.url.path,body))
        if request.url.path.endswith("embeddings"):
            return httpx.Response(200,json={"object":"list","model":"text-embedding-3-small", "data":[{"object":"embedding","index":i,"embedding":[1.0,0.0,0.0]} for i in range(len(body["input"]))],"usage":{"prompt_tokens":10,"total_tokens":10}})
        payload = json.loads(body["input"][1]["content"])
        source = payload["sources"][0]
        draft = {"sentences":[{"text":source["text"],"source_ids":[source["id"]]}],"next_step":"Discuss the source with the local coordinator."}
        return httpx.Response(200,json={"id":"resp_unit_test","object":"response","created_at":1,"status":"completed","model":"test-model",
            "output":[{"id":"msg_unit_test","type":"message","status":"completed","role":"assistant","content":[{"type":"output_text","text":json.dumps(draft),"annotations":[]}]}],
            "usage":{"input_tokens":42,"output_tokens":20,"total_tokens":62},"error":None,"incomplete_details":None})

    with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
        client = OpenAI(api_key="unit-test-placeholder",base_url="https://sdk-contract.test/v1",http_client=http_client,max_retries=0)
        svc = CareService(configured,OpenAIProvider(configured,client=client))
        answer = svc.ask(Actor("participant","HH-001"),"How do we reduce sugar in tea?","en","openai",True)
    assert answer.status == "pending_review" and answer.review_id
    assert len(requests) == 3
    response_request = requests[-1][1]
    assert response_request["store"] is False
    assert response_request["text"]["format"]["type"] == "json_schema"
