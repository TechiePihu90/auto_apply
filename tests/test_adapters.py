import pytest
from adapters import get_adapter
from adapters.base import UserProfile
from adapters.greenhouse import GreenhouseAdapter

SAMPLE_PROFILE = UserProfile(
    first_name="Test",
    last_name="User",
    email="test@example.com",
    phone="555-000-0000",
    resume_path="profile/data/resume.pdf",
)

@pytest.mark.parametrize("url,expected_cls", [
    ("https://boards.greenhouse.io/acme/jobs/12345", "GreenhouseAdapter"),
    ("https://acme.wd1.myworkday.com/applying/job/1", "WorkdayAdapter"),
    ("https://jobs.lever.co/acme/abc-123",            "LeverAdapter"),
    ("https://app.jazz.co/apply/acme/12345",          "JazzHRAdapter"),
    ("https://www.usajobs.gov/job/12345678",           "USAJobsAdapter"),
])
def test_platform_routing(url, expected_cls):
    adapter = get_adapter(url, SAMPLE_PROFILE)
    assert type(adapter).__name__ == expected_cls


def test_greenhouse_profile_values_are_mapped_for_dropdowns_and_text_fields():
    profile = UserProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="555-111-2222",
        resume_path="profile/data/resume.pdf",
        country="United States +1",
        city="New York",
        state="New York",
        custom_answers={
            "requires_sponsorship": "No",
            "authorized_to_work": "Yes",
            "pronounce_name": "Ki-ran",
            "why_company": "I want to work here",
        },
    )
    adapter = GreenhouseAdapter(profile)

    dropdown_map = adapter._build_dropdown_map(profile.custom_answers)
    text_map = adapter._build_text_field_map(profile.custom_answers)

    assert dropdown_map["country"] == "United States"
    assert dropdown_map["state"] == "New York"
    assert dropdown_map["sponsorship"] == "No"
    assert dropdown_map["location"] == "New York"
    assert dropdown_map["legally authorized"] == "Yes"
    assert text_map["city"] == "New York"
    assert text_map["state"] == "New York"
    assert text_map["pronounce"] == "Ki-ran"
    assert text_map["why"] == "I want to work here"


def test_greenhouse_context_matcher_handles_country_and_location_variants():
    profile = UserProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="555-111-2222",
        resume_path="profile/data/resume.pdf",
        country="United States",
        city="New York",
        state="New York",
        location_city="San Francisco",
    )
    adapter = GreenhouseAdapter(profile)

    assert adapter._pick_value_for_context("country of residence", {}) == "United States"
    assert adapter._pick_value_for_context("where are you located", {}) == "San Francisco"
    assert adapter._pick_value_for_context("what city are you in", {}) == "New York"
