"""Automatic authority is independent from manual statements and results."""
from fastapi import HTTPException
from analysis.activity_dfa import METHOD_VERSION, POLICY_PARAMETER_DIGEST, digest
from analysis.dfa_source import AUTO_SDR_ID


def require_policy() -> str:
    from api.dfa_policy import validated_contract
    try:
        contract = validated_contract(AUTO_SDR_ID)
        parameters = {k: v.value for k, v in contract.parameters.items()}
        if contract.model_version != METHOD_VERSION or digest(parameters) != POLICY_PARAMETER_DIGEST:
            raise ValueError("Automatic DFA method differs from its active contract")
        return contract.contract_digest
    except Exception as exc:
        raise HTTPException(503, "DFA_SCIENCE_POLICY_INACTIVE") from exc
