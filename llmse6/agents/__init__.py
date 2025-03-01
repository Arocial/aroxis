import simplellm

from llmse6.config import get_config


def init():
    conf = get_config()
    setup_llm_observability(conf)
    return conf


# Observability & Logging
def setup_llm_observability(conf):
    if conf.observability == "langfuse":
        simplellm.observation.configure_observer("langfuse")
