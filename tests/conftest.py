import pytest
import json
from gltest import get_gl_client, get_accounts

# Ensure gl.UserError is aliased in the local test runner context
try:
    import genlayer.gl as gl
    if not hasattr(gl, "UserError"):
        import genlayer.gl.vm as gl_vm
        gl.UserError = gl_vm.UserError
except Exception:
    pass


def sim_installMocks(mocks: dict, vm=None):
    """
    Installs web and LLM mocks into the GenLayer simulator environment.
    RULE: The parameter sent to sim_installMocks must be a bare dict, NOT wrapped in a list.
    """
    if not isinstance(mocks, dict):
        raise ValueError("sim_installMocks expects a bare dict, not a list or other types.")

    # 1. Install mocks into direct VM context if active
    if vm is not None:
        web_mocks = mocks.get("web_mocks", {})
        for url_pattern, content in web_mocks.items():
            if isinstance(content, dict):
                vm.mock_web(url_pattern, content)
            else:
                vm.mock_web(url_pattern, {"status": 200, "body": str(content)})

        llm_mocks = mocks.get("llm_mocks", {})
        if isinstance(llm_mocks, dict):
            if "verdict" in llm_mocks:
                vm.mock_llm(".*", json.dumps(llm_mocks))
            else:
                for prompt_pattern, resp in llm_mocks.items():
                    resp_str = json.dumps(resp) if isinstance(resp, dict) else str(resp)
                    vm.mock_llm(prompt_pattern, resp_str)
        elif isinstance(llm_mocks, str):
            vm.mock_llm(".*", llm_mocks)

    # 2. Forward to RPC provider if running against live localnet/studionet simulator RPC
    try:
        client = get_gl_client()
        if hasattr(client, "provider") and hasattr(client.provider, "make_request"):
            client.provider.make_request("sim_installMocks", mocks)
    except Exception:
        pass


@pytest.fixture(scope="session")
def gl_accounts():
    """Returns available test accounts."""
    try:
        accs = get_accounts()
        if accs and len(accs) >= 3:
            return accs
    except Exception:
        pass

    from eth_account import Account
    return [
        Account.create("alice"),
        Account.create("bob"),
        Account.create("charlie"),
    ]
