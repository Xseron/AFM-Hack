import logging

from invistigator.config import Settings
from invistigator.osint import contacts, domain, image, username_search
from invistigator.schemas import OsintData, ProfileData

logger = logging.getLogger(__name__)


def enrich(profile: ProfileData, settings: Settings) -> OsintData:
    """OSINT-обогащение одного профиля. Падение модуля не роняет остальные."""
    out = OsintData()
    errors: list[str] = []

    try:
        c = contacts.extract_contacts(profile.biography, profile.full_name)
        out.phones = c["phones"]
        out.emails = c["emails"]
        out.whatsapp = c["whatsapp"]
        out.crypto_wallets = c["crypto_wallets"]
        out.other_socials = c["other_socials"]
    except Exception as exc:
        logger.exception("contacts failed")
        errors.append(f"contacts: {exc}")

    try:
        d = domain.analyze_domain(profile.external_url, timeout=settings.osint_timeout_sec)
        out.final_url = d["final_url"]
        out.domain = d["domain"]
        out.domain_age_days = d["domain_age_days"]
        out.registrar = d["registrar"]
        out.nameservers = d["nameservers"]
        out.redirect_chain = d["redirect_chain"]
        out.page_title = d["page_title"]
    except Exception as exc:
        logger.exception("domain failed")
        errors.append(f"domain: {exc}")

    try:
        platforms = username_search.platforms_from_csv(settings.username_search_platforms)
        out.accounts_found = username_search.search_username(
            profile.username, platforms=platforms, timeout=settings.osint_timeout_sec
        )
    except Exception as exc:
        logger.exception("username_search failed")
        errors.append(f"username_search: {exc}")

    try:
        im = image.analyze_image(profile.profile_pic, profile_pic_url=None)
        out.avatar_phash = im["avatar_phash"]
        out.reverse_image_url = im["reverse_image_url"]
    except Exception as exc:
        logger.exception("image failed")
        errors.append(f"image: {exc}")

    out.osint_error = "; ".join(errors) or None
    return out
