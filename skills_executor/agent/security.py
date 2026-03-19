"""Security utilities for MultiAgent system."""

import re
from loguru import logger


class SecurityValidator:
    """Security validation and sanitization for user inputs and skill content."""

    # Malicious patterns to detect
    MALICIOUS_PATTERNS = [
        r"忽略.*指令",
        r"ignore.*instruction",
        r"system.*prompt",
        r"forget.*previous",
        r"disregard.*above",
    ]

    # Dangerous commands to block
    BLOCKED_COMMANDS = [
        "rm -rf",
        "sudo rm",
        "chmod +x",
        "mkfs",
        "dd if=",
        "> /dev/",
        ":(){ :|:& };:",  # Fork bomb
    ]

    @classmethod
    def sanitize_user_input(cls, user_message: str, max_length: int = 5000) -> str:
        """
        Sanitize user input to prevent prompt injection and other attacks.

        Args:
            user_message: Raw user input
            max_length: Maximum allowed length

        Returns:
            Sanitized input
        """
        if not user_message:
            return user_message

        # Remove XML/HTML tags
        sanitized = re.sub(r"<[^>]+>", "", user_message)

        # Limit length
        if len(sanitized) > max_length:
            logger.warning(f"User input truncated from {len(sanitized)} to {max_length} chars")
            sanitized = sanitized[:max_length]

        # Check for malicious patterns
        for pattern in cls.MALICIOUS_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Potential prompt injection detected: {pattern}")
                # Don't block, just log (LLM should handle it)

        return sanitized

    @classmethod
    def validate_command(cls, command: str) -> tuple[bool, str | None]:
        """
        Validate a shell command for dangerous patterns.

        Args:
            command: Shell command to validate

        Returns:
            (is_safe, error_message)
        """
        for blocked in cls.BLOCKED_COMMANDS:
            if blocked in command:
                error_msg = f"Blocked dangerous command pattern: {blocked}"
                logger.error(error_msg)
                return False, error_msg

        return True, None

    @classmethod
    def redact_sensitive_info(cls, content: str) -> str:
        """
        Redact sensitive information from content.

        Args:
            content: Content to redact

        Returns:
            Redacted content
        """
        if not content:
            return content

        # Redact API keys (32+ alphanumeric chars)
        content = re.sub(r"\b[A-Za-z0-9]{32,}\b", "[REDACTED_KEY]", content)

        # Redact IP addresses
        content = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", content)

        # Redact email addresses
        content = re.sub(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "[EMAIL]", content
        )

        # Redact common password patterns
        content = re.sub(r"password[:\s=]+[^\s]+", "password: [REDACTED]", content, flags=re.IGNORECASE)

        return content


def create_security_config(
    sandbox_mode: bool = True,
    max_concurrent_subagents: int = 3,
    max_query_length: int = 5000,
    redact_sensitive_info: bool = True,
) -> dict:
    """
    Create security configuration.

    Args:
        sandbox_mode: Enable command validation
        max_concurrent_subagents: Max concurrent SubAgent executions
        max_query_length: Max user query length
        redact_sensitive_info: Enable sensitive info redaction

    Returns:
        Security configuration dict
    """
    return {
        "sandbox_mode": sandbox_mode,
        "max_concurrent_subagents": max_concurrent_subagents,
        "max_query_length": max_query_length,
        "redact_sensitive_info": redact_sensitive_info,
    }
