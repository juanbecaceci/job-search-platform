<!--
CV TEMPLATE — Harvard format, ATS-safe, ONE PAGE MAX. Key rules:
- Single page. Verify with pypdf before finalizing.
- Header: email as a mailto link and "LinkedIn" as an absolute hyperlink (not a plain URL).
- Skills section goes ABOVE Experience. One Skills section; adjust the group names below
  to the user's actual skill areas (defined in their professional profile).
- Lead with the profile's flagship case and its validated metrics — never invent or
  embellish metrics. Follow the anonymization rules the user defined in their profile,
  if any (e.g. describing an employer generically instead of naming it).
- Only list skills the user wants surfaced; respect the profile's exclusion list.
- Summary: connect with the target role WITHOUT copying literal phrases from the JD.
- The exporter (core/generate_cv.py) applies the Harvard style to PDF and DOCX.
-->

# {{FULL_NAME}}

{{LOCATION}} | [{{EMAIL}}](mailto:{{EMAIL}}) | [LinkedIn]({{LINKEDIN_URL}})
{{LANGUAGES}}

## Professional Summary

{{PROFESSIONAL_SUMMARY}}

## Skills

- **{{SKILL_GROUP_1}}:** {{SKILLS_1}}
- **{{SKILL_GROUP_2}}:** {{SKILLS_2}}
- **{{SKILL_GROUP_3}}:** {{SKILLS_3}}
- **{{SKILL_GROUP_4}}:** {{SKILLS_4}}
- **{{SKILL_GROUP_5}}:** {{SKILLS_5}}

## Experience

### {{JOB_TITLE_1}} | {{COMPANY_1}}
{{DATE_RANGE_1}} | {{LOCATION_1}}

{{BULLETS_1}}

### {{JOB_TITLE_2}} | {{COMPANY_2}}
{{DATE_RANGE_2}} | {{LOCATION_2}}

{{BULLETS_2}}

### {{JOB_TITLE_3}} | {{COMPANY_3}}
{{DATE_RANGE_3}} | {{LOCATION_3}}

{{BULLETS_3}}

## Education

- {{EDUCATION}}

## Certifications

- {{CERTIFICATIONS}}
