import re


class ResponseCleaner:
    """
    Consolidated response text cleaner class to deduplicate clichés, prompts,
    and thinking blocks across both text (adapter.py) and voice (pipeline.py) pipelines.
    """

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""

        # Strip <think>...</think> blocks
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # Strip stage directions in asterisks (e.g. *sighs*, *nods*, *clears throat*)
        cleaned = re.sub(
            r"\*(sighs|clears throat|nods|smiles|giggles|laughs|chuckles|coughs|shrugs|waves|points|winks|whispers|gasps|yawns|screams|cries|groans|moans|snickers|scoffs|sigh|clear throat|nod|smile|gasp|shrug|yawn)\*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # Strip any remaining markdown formatting asterisks
        cleaned = cleaned.replace("*", "")

        # 1. Clean out the "I don't have that information" prefix for casual queries (jokes/stories/tools)
        cleaned = re.sub(
            r"^[iI] don't have that information\.\s*(If you'd like to hear another type of story or need assistance with something else, feel free to let me know!)?\s*",
            "",
            cleaned,
        )
        cleaned = re.sub(
            r"^[iI] don't have that information\.\s*(If you'd like, I can remember it for next time we chat!)?\s*",
            "",
            cleaned,
        )
        cleaned = re.sub(
            r"^[iI] don't have that information\.\s*(I'm Sentri, here to assist with any questions or tasks within my capabilities!?)?\s*",
            "",
            cleaned,
        )
        cleaned = re.sub(r"^[iI] don't have that information\.\s*", "", cleaned)

        # 2. Strip generic customer support clichés programmatically ONLY at the very end of the string.
        # Uses loose matching to catch variants (e.g. "this fine day", "further today", "resources", "instruments").
        cliches = [
            r"\b[hH]ow (can|may|else may|else can) I (further |help |assist |serve ).*\??\s*$",
            r"\b[iI]s there anything else (you would prefer to discuss|I can help|I can assist|you'd like|you would prefer).*\??\s*$",
            r"\b[wW]hat else can I (do|help).*\??\s*$",
            r"\b[hH]ow may these .* serve us today\??\s*$",
            r"\b[iI]'m Sentri, (here to assist|here to help).*\s*$",
            r"\b[hH]ow (?:can|may|else may|else can) (?:I |Sentri |we )(?:further |help |assist |serve |be of service).*$",
            r"\b[wW]hat (?:can|else can) (?:I |Sentri )(?:do|help).*$",
            r"\b[iI]s there anything (?:else |specific |)(?:you|I|that).*$",
            r"\b[iI]f there'?s anything.*(?:let me know|I can help|assist).*$",
            r"\b[hH]ow(?:'s| is) your (?:day|evening|night|morning).*$",
            r"\b[hH]ow may we continue\??.*$",
            r"\b[fF]eel free to (?:ask|reach out|let me know).*$",
            r"\b[pP]lease (?:feel free|let me know|don't hesitate).*$",
            r"\b[iI]'?m (?:here|ready|at your service).*(?:assist|help|for you|for any).*$",
            r"\b[iI] am here and ready.*$",
            r"\b[yY]our feedback is important.*$",
            r"\b[tT]hank you for (?:bringing|asking|your).*$",
            r"[—–-]\s*[iI]'?m here now.*$",
        ]

        for cliche in cliches:
            cleaned = re.sub(cliche, "", cleaned, flags=re.IGNORECASE)

        # Collapse multiple horizontal spaces/tabs into a single space
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return cleaned.strip()
