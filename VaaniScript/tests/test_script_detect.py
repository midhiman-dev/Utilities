from vaaniscript.lang import detect_script_language


def test_detects_devanagari_text_as_hindi() -> None:
    result = detect_script_language("नमस्ते दुनिया")

    assert result.detected_lang == "hi"
    assert result.devanagari_count > 0
    assert result.bengali_count == 0
    assert result.confidence == 1.0
    assert result.flags == []


def test_detects_bengali_text_as_bengali() -> None:
    result = detect_script_language("হ্যালো পৃথিবী")

    assert result.detected_lang == "bn"
    assert result.bengali_count > 0
    assert result.devanagari_count == 0
    assert result.confidence == 1.0
    assert result.flags == []


def test_latin_only_text_is_unknown() -> None:
    result = detect_script_language("hello office meeting")

    assert result.detected_lang == "unknown"
    assert result.devanagari_count == 0
    assert result.bengali_count == 0
    assert result.other_letter_count == len("helloofficemeeting")
    assert result.confidence == 0.0
    assert result.flags == ["no_indic_script"]


def test_empty_or_whitespace_text_is_unknown() -> None:
    result = detect_script_language("   \n\t  ")

    assert result.detected_lang == "unknown"
    assert result.devanagari_count == 0
    assert result.bengali_count == 0
    assert result.other_letter_count == 0
    assert result.flags == ["no_indic_script"]


def test_embedded_english_words_do_not_override_hindi_detection() -> None:
    result = detect_script_language("कल office meeting है")

    assert result.detected_lang == "hi"
    assert result.devanagari_count > 0
    assert result.bengali_count == 0
    assert result.other_letter_count > 0
    assert result.confidence == 1.0


def test_embedded_english_words_do_not_override_bengali_detection() -> None:
    result = detect_script_language("কাল office meeting আছে")

    assert result.detected_lang == "bn"
    assert result.bengali_count > 0
    assert result.devanagari_count == 0
    assert result.other_letter_count > 0
    assert result.confidence == 1.0


def test_mixed_hindi_and_bengali_scripts_without_clear_winner_are_ambiguous() -> None:
    result = detect_script_language("नमस्ते হ্যালো")

    assert result.detected_lang == "ambiguous"
    assert result.devanagari_count > 0
    assert result.bengali_count > 0
    assert 0.0 < result.confidence < 0.7
    assert result.flags == ["lang_ambiguous"]


def test_mixed_scripts_with_clear_bengali_winner_return_bengali() -> None:
    result = detect_script_language("আমি বাংলা বলি नम")

    assert result.detected_lang == "bn"
    assert result.bengali_count > result.devanagari_count
    assert result.confidence >= 0.7
    assert result.flags == []
