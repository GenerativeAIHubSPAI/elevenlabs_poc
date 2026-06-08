# app/core/knowledge_sources.py

from enum import StrEnum


class KnowledgeSource(StrEnum):
    CACHE = "cache"
    INSURANCE_COMPANY = "insurance_company"
    FLIGHT_ATTENDANT = "flight_attendant"
    GACHAPON_DISTRIBUTION = "gachapon_distribution"


STATIC_BUSINESS_EXAMPLES = {
    KnowledgeSource.INSURANCE_COMPANY: {
        "label": "Insurance Company",
        "namespace": "insurance_company",
        "description": "Customer-service assistant for insurance policy, claims, coverage, and support questions.",
    },
    KnowledgeSource.FLIGHT_ATTENDANT: {
        "label": "Flight Attendant",
        "namespace": "flight_attendant",
        "description": "Passenger-service assistant for airline, cabin, safety, and travel support questions.",
    },
    KnowledgeSource.GACHAPON_DISTRIBUTION: {
        "label": "Gachapon Distribution",
        "namespace": "gachapon_distribution",
        "description": "Client-service assistant for gachapon products, machines, capsules, stock, maintenance, and distribution.",
    },
}


def build_cache_namespace(session_id: str) -> str:
    return f"cache:{session_id}"


def resolve_knowledge_namespaces(
    knowledge_source: str,
    session_id: str,
    include_uploaded_pdfs: bool = False,
) -> list[str]:
    if knowledge_source == KnowledgeSource.CACHE:
        return [build_cache_namespace(session_id)]

    if knowledge_source not in STATIC_BUSINESS_EXAMPLES:
        raise ValueError(f"Unknown knowledge source: {knowledge_source}")

    namespaces = [STATIC_BUSINESS_EXAMPLES[KnowledgeSource(knowledge_source)]["namespace"]]

    if include_uploaded_pdfs:
        namespaces.insert(0, build_cache_namespace(session_id))

    return namespaces