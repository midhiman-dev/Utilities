from vaaniscript.translate import FakeTranslator, IndicTransTranslator, NoOpTranslator, TranslationOutput


def test_indictrans_translator_is_lazy_on_init(monkeypatch) -> None:
    def fail_import(name: str):
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr("vaaniscript.translate.indictrans.import_module", fail_import)

    translator = IndicTransTranslator(model_name="custom-model")

    assert translator.model_name == "custom-model"


def test_fake_translator_is_deterministic() -> None:
    translator = FakeTranslator()

    output = translator.translate(text="\u0928\u092e\u0938\u094d\u0924\u0947 office", source_lang="hi")

    assert output == TranslationOutput(english_text="[hi->en] \u0928\u092e\u0938\u094d\u0924\u0947 office")
    assert translator.calls == [("\u0928\u092e\u0938\u094d\u0924\u0947 office", "hi", "en")]


def test_noop_translator_returns_empty_english_text() -> None:
    translator = NoOpTranslator()

    output = translator.translate(text="\u09ac\u09a8\u09cd\u09a7\u09c1", source_lang="bn")

    assert output == TranslationOutput(english_text="")
