"""Profile management for WB CLI multi-account support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from wb.core.constants import (
    ALL_CATEGORY,
    DEFAULT_PROFILE_NAME,
    DEFAULT_TOKEN_TYPE,
    PROFILES_FILE,
    TOKEN_CATEGORIES,
    TOKEN_TYPES,
)
from wb.core.exceptions import ConfigError, ValidationError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Profile:
    """A named authentication profile.

    Attributes:
        name: Profile identifier.
        tokens: Mapping of category -> token string.
        token_type: One of :data:`wb.core.constants.TOKEN_TYPES`. Drives
            the bootstrap rate-limit prior selection in
            :func:`wb.core.rate_limits.select_prior`. Single value
            applies to every category in ``tokens``; in practice a
            seller's tokens are all the same type. Defaults to
            :data:`wb.core.constants.DEFAULT_TOKEN_TYPE` (``'base'``)
            for legacy profiles missing the field.
        created_at: ISO timestamp of profile creation.
        last_used: ISO timestamp of last usage.
    """

    name: str
    tokens: dict[str, str] = field(default_factory=dict)
    portal_session: dict[str, str] = field(default_factory=dict)
    token_type: str = DEFAULT_TOKEN_TYPE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used: str | None = None
    seller_id: str | None = None

    def has_token(self, category: str) -> bool:
        """Check if profile has a token for the given category."""
        return category in self.tokens and bool(self.tokens[category])

    def get_token(self, category: str) -> str:
        """Get token for a category.

        Raises:
            ValidationError: If token is not set for this category.
        """
        if not self.has_token(category):
            raise ValidationError(
                f'Profile {self.name!r} has no token for category {category!r}'
            )
        return self.tokens[category]

    def set_token(self, category: str, token: str) -> None:
        """Set token for a category.

        Raises:
            ValidationError: If category is not recognized.
        """
        if category not in TOKEN_CATEGORIES:
            raise ValidationError(
                f'Unknown token category {category!r}. '
                f'Valid categories: {TOKEN_CATEGORIES}'
            )
        self.tokens[category] = token

    def has_portal_session(self) -> bool:
        """Check if profile has portal session credentials."""
        return 'authorizev3' in self.portal_session and bool(self.portal_session['authorizev3'])

    def get_portal_session(self) -> dict[str, str] | None:
        """Get portal session data, or None if not configured."""
        if not self.has_portal_session():
            return None
        return dict(self.portal_session)

    def set_portal_session(
            self,
            authorizev3: str,
            cookie: str | None = None,
            session_token: str | None = None,
            user_id: str | None = None,
            exp: str | None = None,
    ) -> None:
        """Store portal session credentials.

        Args:
            authorizev3: The authorizev3 header value.
            cookie: Browser cookie string.
            session_token: Session JWT from portal auth endpoint.
            user_id: Seller user ID from portal auth response.
            exp: Token expiration timestamp from portal auth response.
        """
        self.portal_session = {'authorizev3': authorizev3}
        if cookie:
            self.portal_session['cookie'] = cookie
        if session_token:
            self.portal_session['session_token'] = session_token
        if user_id:
            self.portal_session['user_id'] = user_id
        if exp:
            self.portal_session['exp'] = exp

    def touch(self) -> None:
        """Update last_used timestamp."""
        self.last_used = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        data = {
            'name': self.name,
            'tokens': self.tokens,
            'token_type': self.token_type,
            'created_at': self.created_at,
            'last_used': self.last_used,
        }
        if self.portal_session:
            data['portal_session'] = self.portal_session
        if self.seller_id:
            data['seller_id'] = self.seller_id
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        """Deserialize from dict.

        Legacy profiles missing ``token_type`` default to
        :data:`DEFAULT_TOKEN_TYPE` (Base) — the safer assumption.
        """
        return cls(
            name=data['name'],
            tokens=data.get('tokens', {}),
            portal_session=data.get('portal_session', {}),
            token_type=data.get('token_type', DEFAULT_TOKEN_TYPE),
            created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
            last_used=data.get('last_used'),
            seller_id=data.get('seller_id'),
        )


class ProfileStore:
    """Manages profiles on local filesystem.

    Attributes:
        config_dir: Directory to store profile data.
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._profiles_path = config_dir / PROFILES_FILE
        self._active_profile: str = DEFAULT_PROFILE_NAME
        self._profiles: dict[str, Profile] = {}
        self._load()

    def _load(self) -> None:
        """Load profiles from disk."""
        if not self._profiles_path.exists():
            return
        try:
            data = json.loads(self._profiles_path.read_text(encoding='utf-8'))
            self._active_profile = data.get('active', DEFAULT_PROFILE_NAME)
            for profile_data in data.get('profiles', []):
                profile = Profile.from_dict(profile_data)
                self._profiles[profile.name] = profile
        except (json.JSONDecodeError, KeyError) as exc:
            raise ConfigError(
                f'Corrupted profiles file: {self._profiles_path}'
            ) from exc

    def _save(self) -> None:
        """Persist profiles to disk."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            'active': self._active_profile,
            'profiles': [p.to_dict() for p in self._profiles.values()],
        }
        self._profiles_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

    @property
    def active_profile_name(self) -> str:
        """Name of the currently active profile."""
        return self._active_profile

    def list_profiles(self) -> list[Profile]:
        """Return all stored profiles."""
        return list(self._profiles.values())

    def get_profile(self, name: str | None = None) -> Profile:
        """Get a profile by name, defaulting to active.

        Raises:
            ConfigError: If profile does not exist.
        """
        target = name or self._active_profile
        if target not in self._profiles:
            raise ConfigError(f'Profile {target!r} does not exist')
        return self._profiles[target]

    def create_profile(self, name: str) -> Profile:
        """Create a new profile.

        Raises:
            ValidationError: If profile already exists.
        """
        if name in self._profiles:
            raise ValidationError(f'Profile {name!r} already exists')
        profile = Profile(name=name)
        self._profiles[name] = profile
        self._save()
        return profile

    def set_active(self, name: str) -> None:
        """Set the active profile.

        Raises:
            ConfigError: If profile does not exist.
        """
        if name not in self._profiles:
            raise ConfigError(f'Profile {name!r} does not exist')
        self._active_profile = name
        self._save()

    def save_token(self, profile_name: str, category: str, token: str) -> None:
        """Save a token to a profile, creating it if needed.

        If category is ALL_CATEGORY ('all'), saves the token under every
        category in TOKEN_CATEGORIES.
        """
        if profile_name not in self._profiles:
            self.create_profile(profile_name)
        profile = self._profiles[profile_name]
        categories = TOKEN_CATEGORIES if category == ALL_CATEGORY else [category]
        for cat in categories:
            profile.set_token(cat, token)
        self._save()

    def set_token_type(self, profile_name: str, token_type: str) -> None:
        """Persist the token type on a profile.

        Args:
            profile_name: Existing profile name.
            token_type: One of :data:`wb.core.constants.TOKEN_TYPES`.

        Raises:
            ConfigError: When the profile doesn't exist.
            ValidationError: When ``token_type`` isn't a known value.
        """
        if profile_name not in self._profiles:
            raise ConfigError(f'Profile {profile_name!r} does not exist')
        if token_type not in TOKEN_TYPES:
            raise ValidationError(
                f'Unknown token type {token_type!r}. '
                f'Valid types: {", ".join(TOKEN_TYPES)}'
            )
        self._profiles[profile_name].token_type = token_type
        self._save()

    def save_portal_session(
            self,
            profile_name: str,
            authorizev3: str,
            cookie: str | None = None,
            session_token: str | None = None,
            user_id: str | None = None,
            exp: str | None = None,
    ) -> None:
        """Save portal session credentials to a profile, creating it if needed."""
        if profile_name not in self._profiles:
            self.create_profile(profile_name)
        profile = self._profiles[profile_name]
        profile.set_portal_session(
            authorizev3=authorizev3,
            cookie=cookie,
            session_token=session_token,
            user_id=user_id,
            exp=exp,
        )
        self._save()

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Raises:
            ConfigError: If profile does not exist.
            ValidationError: If trying to delete the active profile.
        """
        if name not in self._profiles:
            raise ConfigError(f'Profile {name!r} does not exist')
        if name == self._active_profile:
            raise ValidationError(
                'Cannot delete the active profile. Switch to another profile first.'
            )
        del self._profiles[name]
        self._save()
