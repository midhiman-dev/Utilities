from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Protocol


SUPPORTED_TRANSLATION_ROUTES = {("hi", "en"), ("bn", "en")}


@dataclass(slots=True)
class TranslationOutput:
    english_text: str
    flags: list[str] = field(default_factory=list)


class Translator(Protocol):
    def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> TranslationOutput:
        """Translate a single segment into English."""


@dataclass(slots=True)
class FakeTranslator:
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> TranslationOutput:
        self.calls.append((text, source_lang, target_lang))
        return TranslationOutput(english_text=f"[{source_lang}->{target_lang}] {text}")


class NoOpTranslator:
    """Default runtime stub when a real translation backend is not configured."""

    def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> TranslationOutput:
        return TranslationOutput(english_text="")


class IndicTransTranslator:
    def __init__(
        self,
        model_name: str = "ai4bharat/indictrans2-en-indic-dist-200M",
        *,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._processor: Any | None = None

    def translate(
        self,
        *,
        text: str,
        source_lang: str,
        target_lang: str = "en",
    ) -> TranslationOutput:
        if (source_lang, target_lang) not in SUPPORTED_TRANSLATION_ROUTES:
            raise ValueError(f"Unsupported translation route: {source_lang}->{target_lang}")

        processor, tokenizer, model = self._get_runtime()
        prepared_batch = processor.preprocess_batch(
            [text],
            src_lang=source_lang,
            tgt_lang=target_lang,
        )
        tokenized = tokenizer(
            prepared_batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        if hasattr(tokenized, "to"):
            tokenized = tokenized.to(self.device)
        generated_tokens = model.generate(**tokenized)
        decoded = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
        translated = processor.postprocess_batch(decoded, lang=target_lang)
        english_text = translated[0].strip() if translated else ""
        return TranslationOutput(english_text=english_text)

    def _get_runtime(self) -> tuple[Any, Any, Any]:
        if self._processor is not None and self._tokenizer is not None and self._model is not None:
            return self._processor, self._tokenizer, self._model

        transformers = import_module("transformers")
        toolkit = import_module("IndicTransToolkit")

        auto_tokenizer = getattr(transformers, "AutoTokenizer")
        auto_model = getattr(transformers, "AutoModelForSeq2SeqLM")
        processor_cls = getattr(toolkit, "IndicProcessor")

        self._tokenizer = auto_tokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            local_files_only=True,
        )
        self._model = auto_model.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            local_files_only=True,
        )
        if hasattr(self._model, "to"):
            self._model = self._model.to(self.device)
        self._processor = processor_cls(inference=True)
        return self._processor, self._tokenizer, self._model
