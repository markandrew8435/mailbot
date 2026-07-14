DEFAULT_SUBJECT = "Quick Question"

DEFAULT_BODY_TEMPLATE = """Hi {name},

I came across your profile and wanted to connect regarding roles at {company}.

Regards,
Mark
"""

def format_template(body_template: str, email: str, name: str = "", company: str = "") -> str:
    """
    Interpolates variables (name, company, email) into the outreach email template.
    Provides standard fallback defaults if name or company are not supplied.
    """
    if not name or name.strip() == "":
        name = "there"
    if not company or company.strip() == "":
        company = "your company"
        
    return body_template.format(
        name=name.strip(),
        company=company.strip(),
        email=email.strip()
    )
