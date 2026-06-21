import io
import pytest
from mask_core import (
    mask_phone_numbers,
    process_stream,
    run_selftest,
    SELF_TEST_CASES,
)


@pytest.mark.parametrize("input_text, expected_output", SELF_TEST_CASES)
def test_self_test_cases(input_text, expected_output):
    """Verify that all default self-test cases produce identical output."""
    got, _ = mask_phone_numbers(input_text)
    assert got == expected_output


def test_timestamp_not_masked():
    """Verify WhatsApp style timestamps are completely ignored by the pattern."""
    timestamp = "21/06/2026, 09:05 - David: hi"
    got, count = mask_phone_numbers(timestamp)
    assert got == timestamp
    assert count == 0


def test_comma_separated_numbers():
    """Verify that numbers with thousands commas (like currency) are not masked."""
    text = "Total: 1,23,456 rupees"
    got, count = mask_phone_numbers(text)
    assert got == text
    assert count == 0


def test_no_separator_number():
    """Verify that a number with no separators (but prefixed) gets masked."""
    text = "+919845012345"
    got, count = mask_phone_numbers(text)
    assert got == "+XXXXXXXXXXXX"
    assert count == 1


def test_multiple_numbers_per_line():
    """Verify that multiple valid numbers on a single line are all masked."""
    text = "Two numbers: +91 98450 12345 and +91 99000 54321"
    expected = "Two numbers: +XX XXXXX XXXXX and +XX XXXXX XXXXX"
    got, count = mask_phone_numbers(text)
    assert got == expected
    assert count == 2


def test_bracketed_number():
    """Verify bracketed numbers mask correct parts while keeping brackets."""
    text = "David [+91 98450 12345]: hi"
    expected = "David [+XX XXXXX XXXXX]: hi"
    got, count = mask_phone_numbers(text)
    assert got == expected
    assert count == 1


def test_whatsapp_header_colon_number():
    """Verify phone numbers followed by a colon (WhatsApp headers) are fully masked."""
    text1 = "[10:58, 21/06/2026] +91 86523 89284: Can someone help me"
    expected1 = "[10:58, 21/06/2026] +XX XXXXX XXXXX: Can someone help me"
    got1, count1 = mask_phone_numbers(text1)
    assert got1 == expected1
    assert count1 == 1

    text2 = "[11:24, 21/06/2026] +91 836 934 3261: Can someone help me"
    expected2 = "[11:24, 21/06/2026] +XX XXX XXX XXXX: Can someone help me"
    got2, count2 = mask_phone_numbers(text2)
    assert got2 == expected2
    assert count2 == 1



def test_loose_mode():
    """Verify loose mode masks numbers without leading + or 00 prefix."""
    text = "Call (123) 456-7890 or 98450 12345"
    expected = "Call (XXX) XXX-XXXX or XXXXX XXXXX"
    got, count = mask_phone_numbers(text, require_plus=False)
    assert got == expected
    assert count == 2


def test_strict_mode_skips_bare():
    """Verify default strict mode does NOT mask numbers without leading + or 00."""
    text = "Call (123) 456-7890 or 98450 12345"
    # Under require_plus=True, neither has + or 00 prefix, so they shouldn't change
    got, count = mask_phone_numbers(text, require_plus=True)
    assert got == text
    assert count == 0


def test_min_max_digits():
    """Verify custom min/max digit filters are respected."""
    text = "+91 9845"  # 6 digits (too short if min=7)
    got, count = mask_phone_numbers(text, min_digits=7)
    assert got == text
    assert count == 0

    text_ok = "+91 98450"  # 7 digits
    got_ok, count_ok = mask_phone_numbers(text_ok, min_digits=7)
    assert got_ok == "+XX XXXXX"
    assert count_ok == 1

    text_long = "+91 98450 12345 67890"  # 17 digits (too long if max=15)
    got_long, count_long = mask_phone_numbers(text_long, max_digits=15)
    assert got_long == text_long
    assert count_long == 0


def test_process_stream():
    """Verify stream processing line-by-line matches direct string masking."""
    input_lines = [
        "Hello World\n",
        "Phone: +91 98450 12345\n",
        "No number here\n",
        "Another: +1-555-123-4567\n",
    ]
    infile = io.StringIO("".join(input_lines))
    outfile = io.StringIO()
    
    total = process_stream(infile, outfile)
    assert total == 2
    
    output_lines = outfile.getvalue().splitlines(keepends=True)
    assert output_lines[0] == "Hello World\n"
    assert output_lines[1] == "Phone: +XX XXXXX XXXXX\n"
    assert output_lines[2] == "No number here\n"
    assert output_lines[3] == "Another: +X-XXX-XXX-XXXX\n"


def test_unicode_preservation():
    """Verify Unicode/non-ASCII characters and emojis are fully preserved."""
    # Emojis and Kannada text + phone number
    text = "ನಮಸ್ಕಾರ 👋 +91 98450 12345 শুভ সকাল"
    expected = "ನಮಸ್ಕಾರ 👋 +XX XXXXX XXXXX শুভ সকাল"
    got, count = mask_phone_numbers(text)
    assert got == expected
    assert count == 1


def test_empty_input():
    """Verify empty input behaves gracefully."""
    got, count = mask_phone_numbers("")
    assert got == ""
    assert count == 0


def test_run_selftest():
    """Verify that run_selftest() succeeds."""
    assert run_selftest() is True
