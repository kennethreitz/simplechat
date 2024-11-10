import contextlib
import os
import re
from typing import ClassVar, List
from pathlib import PosixPath

import spacy
import nltk
import simplemind as sm

from .db import Database
from .settings import get_db_path

from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag

import traceback

import time


class SimpleMemoryPlugin(sm.BasePlugin):
    model_config = {"extra": "allow"}

    db_path: ClassVar[PosixPath] = get_db_path()
    db_url: ClassVar[str] = f"sqlite:///{db_path}"
    db: ClassVar[Database] = Database(db_path=db_url)

    # Consolidate class variables and add type hints
    nlp: ClassVar[spacy.language.Language] = spacy.load("en_core_web_sm")

    # Move patterns to class variable for better organization
    ESSENCE_PATTERNS: ClassVar[dict] = {
        "value": [
            r"I (?:really )?(?:believe|think) (?:that )?(.+)",
            r"(?:It's|Its) important (?:to me )?that (.+)",
            r"I value (.+)",
            r"(?:The )?most important (?:thing|aspect) (?:to me )?is (.+)",
        ],
        "identity": [
            r"I am(?: a| an)? (.+)",
            r"I consider myself(?: a| an)? (.+)",
            r"I identify as(?: a| an)? (.+)",
        ],
        "preference": [
            r"I (?:really )?(?:like|love|enjoy|prefer) (.+)",
            r"I can't stand (.+)",
            r"I hate (.+)",
            r"I always (.+)",
            r"I never (.+)",
        ],
        "emotion": [
            r"I feel (.+)",
            r"I'm feeling (.+)",
            r"(?:It|That) makes me feel (.+)",
        ],
    }

    # Change from ClassVar to instance variable
    personal_identity: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize database tables
        self.db.migrate()
        # Download NLTK dependencies
        self.setup_deps()

    def setup_deps(self):
        """Downloads the dependencies for nltk."""

        with open(os.devnull, "w") as null_out:
            with (
                contextlib.redirect_stdout(null_out),
                contextlib.redirect_stderr(null_out),
            ):
                nltk.download("punkt", quiet=True)
                nltk.download("averaged_perceptron_tagger", quiet=True)

    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities with improved filtering"""
        doc = self.nlp(text)

        # Define important entity types with more granular categories
        important_types = {
            "PERSON",  # Names of people
            "ORG",  # Companies, agencies, institutions
            "GPE",  # Countries, cities, states
            "NORP",  # Nationalities, religious or political groups
            "PRODUCT",  # Products
            "EVENT",  # Named events
            "WORK_OF_ART",  # Titles of books, songs, etc.
            "FAC",  # Buildings, airports, highways, etc.
            "LOC",  # Non-GPE locations, mountain ranges, water bodies
            "LANGUAGE",  # Named languages
            "TECH",  # Technical terms, programming languages
        }

        # Custom rules for technical terms
        tech_patterns = [
            "Python",
            "JavaScript",
            "Java",
            "C\\+\\+",
            "Ruby",
            "TypeScript",
            "React",
            "Angular",
            "Vue",
            "Node\\.js",
            "Docker",
            "Kubernetes",
            "AWS",
            "Azure",
            "Git",
            "GitHub",
            "VS Code",
            "Visual Studio",
            "Linux",
            "Windows",
            "MacOS",
            "iOS",
            "Android",
        ]

        entities = []

        # Process standard spaCy entities
        for ent in doc.ents:
            if (
                ent.label_ in important_types
                and len(ent.text.strip()) > 1
                and not ent.text.strip().isnumeric()
            ):
                entities.append(ent.text.strip())

        # Process custom tech patterns
        for pattern in tech_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(match.group())

        # Clean and normalize entities
        cleaned_entities = []
        for entity in entities:
            entity = entity.strip()
            # Remove any leading/trailing punctuation
            entity = re.sub(r"^[\W_]+|[\W_]+$", "", entity)
            # Only add if entity is meaningful
            if len(entity) > 1 and not entity.isnumeric():
                cleaned_entities.append(entity)

        return list(set(cleaned_entities))

    def format_context_message(self, entities: List[tuple]) -> str:
        """Format context message with essence markers and identity"""
        context_parts = []

        # Add identity if available
        if self.personal_identity:
            context_parts.append(f"Current user: {self.personal_identity}")

        # Add essence markers
        essence_markers = self.retrieve_essence_markers()
        if essence_markers:
            markers_by_type = {}
            for marker_type, marker_text in essence_markers:
                markers_by_type.setdefault(marker_type, []).append(marker_text)

            context_parts.append("User characteristics:")
            for marker_type, markers in markers_by_type.items():
                context_parts.append(f"- {marker_type.title()}: {', '.join(markers)}")

        # Add entity context with user/llm breakdown
        if entities:
            entity_strings = []
            for entity, total, user_count, llm_count in entities:
                if total > 0:  # Only include if there are mentions
                    entity_strings.append(
                        f"{entity} (mentioned {total} times - User: {user_count}, AI: {llm_count})"
                    )

            if entity_strings:
                if len(entity_strings) > 1:
                    topics = (
                        ", ".join(entity_strings[:-1]) + f" and {entity_strings[-1]}"
                    )
                else:
                    topics = entity_strings[0]
                context_parts.append(f"Recent conversation topics: {topics}")

        # Only return if we have actual content
        if context_parts:
            return "\n".join(context_parts)
        return ""  # Return empty string if no context to add

    def extract_essence_markers(self, text: str) -> List[tuple[str, str]]:
        """Extract essence markers from text."""
        markers = []
        doc = self.nlp(text)

        for sent in doc.sents:
            sent_text = sent.text.strip().lower()

            for marker_type, pattern_list in self.ESSENCE_PATTERNS.items():
                for pattern in pattern_list:
                    for match in re.finditer(pattern, sent_text, re.IGNORECASE):
                        marker_text = match.group(1).strip()
                        if self._is_valid_marker(marker_text):
                            markers.append((marker_type, marker_text))

        return markers

    def _is_valid_marker(self, marker_text: str) -> bool:
        """Helper method to validate essence markers"""
        invalid_words = {"um", "uh", "like"}
        return len(marker_text) > 3 and not any(w in marker_text for w in invalid_words)

    def pre_send_hook(self, conversation: sm.Conversation) -> bool:
        """Process user message before sending to LLM"""
        self.llm_model = conversation.llm_model
        self.llm_provider = conversation.llm_provider

        last_message = conversation.get_last_message(role="user")
        if not last_message:
            return True

        # Check for identity statement first
        if identity := self.extract_identity(last_message.text):
            self.store_identity(identity)

        # Check if this is an identity question
        elif self.is_identity_question(last_message.text):
            identity = self.load_identity()
            if identity:
                response = f"You previously identified yourself as {identity}."
                conversation.add_message(role="assistant", text=response)

        # Process entities and markers
        self._process_user_message(last_message.text)
        self._add_context_to_conversation(conversation)

        return True

    def _process_user_message(self, message: str) -> None:
        """Process user message for entities and markers"""
        # Extract and store entities
        entities = self.extract_entities(message)
        for entity in entities:
            self.store_entity(entity, source="user")

        # Extract and store essence markers
        essence_markers = self.extract_essence_markers(message)
        for marker_type, marker_text in essence_markers:
            self.store_essence_marker(marker_type, marker_text)

    def _add_context_to_conversation(self, conversation: sm.Conversation) -> None:
        """Add context message to conversation"""
        # Load identity if not already set
        if self.personal_identity is None:
            self.personal_identity = self.load_identity()

        # Update last seen if we have an identity
        if self.personal_identity:
            max_retries = 3
            retry_delay = 0.1
            for attempt in range(max_retries):
                try:
                    self.db.update_last_seen(self.personal_identity)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        print(
                            f"Warning: Could not update last_seen after {max_retries} attempts: {str(e)}"
                        )

        # Limit to recent entities from the last 30 days
        recent_entities = self.retrieve_recent_entities(days=30)

        # Trim conversation history to last 12 messages
        conversation.messages = conversation.messages[-12:]

        context_message = self.format_context_message(recent_entities)
        if context_message.strip():
            conversation.add_message(role="user", text=context_message)

    def store_entity(self, entity: str, source: str = "user") -> None:
        """Store entity with retry logic"""
        max_retries = 3
        retry_delay = 0.1  # seconds

        for attempt in range(max_retries):
            try:
                if not entity or len(entity.strip()) < 2:
                    return
                self.db.store_entity(entity, source)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(
                        f"Failed to store entity after {max_retries} attempts: {str(e)}"
                    )

    def store_identity(self, identity: str) -> None:
        """Store identity in database and update class variable with retry logic"""
        max_retries = 3
        retry_delay = 0.1  # seconds

        for attempt in range(max_retries):
            try:
                self.db.query(
                    """
                    INSERT INTO identity (identity, created_at, last_seen)
                    VALUES (:identity, datetime('now'), datetime('now'))
                    ON CONFLICT(identity) DO UPDATE SET
                        last_seen = datetime('now')
                    """,
                    identity=identity,
                )
                self.personal_identity = identity
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(
                        f"Failed to store identity after {max_retries} attempts: {str(e)}"
                    )

    def load_identity(self) -> str | None:
        """Load most recent identity from database with retry logic"""
        max_retries = 3
        retry_delay = 0.1  # seconds

        for attempt in range(max_retries):
            try:
                result = self.db.query(
                    """
                    SELECT identity FROM identity
                    ORDER BY last_seen DESC
                    LIMIT 1
                    """
                ).first()
                self.personal_identity = result.identity if result else None
                return self.personal_identity
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return None

    def store_essence_marker(self, marker_type: str, marker_text: str) -> None:
        """Store essence marker with retry logic"""
        max_retries = 3
        retry_delay = 0.1  # seconds

        for attempt in range(max_retries):
            try:
                self.db.store_essence_marker(marker_type, marker_text)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(
                        f"Failed to store marker after {max_retries} attempts: {str(e)}"
                    )

    def retrieve_essence_markers(self, days: int = 30) -> List[tuple[str, str]]:
        """Retrieve essence markers with debug logging"""
        try:
            markers = self.db.retrieve_essence_markers(days)
            return markers
        except Exception as e:
            print(f"ERROR retrieving markers: {e}")
            traceback.print_exc()
            return []

    def summarize_memory(self, days: int = 30) -> str:
        """Consolidate recent conversation memory into a summary"""
        entities = self.retrieve_recent_entities(days=days)
        if not entities:
            return "No recent conversation history to consolidate."

        # Group entities by frequency
        frequent = []
        occasional = []

        for entity, total, user_count, llm_count in entities:
            if total >= 3:
                frequent.append(f"{entity} (mentioned {total} times)")
            else:
                occasional.append(f"{entity} (mentioned {total} times)")

        # Build summary
        summary_parts = []

        if self.personal_identity:
            summary_parts.append(f"User Identity: {self.personal_identity}")

        if frequent:
            summary_parts.append("Frequently Discussed Topics:")
            summary_parts.extend([f"- {item}" for item in frequent])

        if occasional:
            summary_parts.append("Other Topics Mentioned:")
            summary_parts.extend([f"- {item}" for item in occasional])

        return "\n".join(summary_parts)

    def retrieve_recent_entities(self, days: int = 7) -> List[tuple]:
        """Retrieve recently mentioned entities with their frequency data."""
        try:
            entities = self.db.retrieve_recent_entities(days)
            return entities
        except Exception as e:
            print(f"ERROR retrieving entities: {e}")
            traceback.print_exc()
            return []

    def post_response_hook(self, conversation: sm.Conversation) -> None:
        """Process assistant's response after it's received."""
        try:
            last_message = conversation.get_last_message(role="assistant")
            if not last_message or not last_message.text:
                return

            message_text = last_message.text
            entities = self.extract_entities(message_text)

            if entities:
                for entity in entities:
                    try:
                        self.store_entity(entity, source="llm")
                    except Exception as e:
                        print(f"✗ Failed to store entity {entity}: {str(e)}")

        except Exception as e:
            print(f"Error in post_response_hook: {str(e)}")
            traceback.print_exc()

    def extract_identity(self, text: str) -> str | None:
        """Extract identity statements from text."""
        text = text.lower().strip()

        identity_patterns = [
            (r"^i am (.+)$", 1),
            (r"^my name is (.+)$", 1),
            (r"^call me (.+)$", 1),
            (r"^i'm (.+)$", 1),  # Add pattern for "I'm"
            (r"^hey i'm (.+)$", 1),  # Add pattern for "hey I'm"
            (r"^hello i'm (.+)$", 1),  # Add pattern for "hello I'm"
            (r"^hi i'm (.+)$", 1),  # Add pattern for "hi I'm"
        ]

        for pattern, group in identity_patterns:
            if match := re.match(pattern, text):
                identity = match.group(group).strip()
                return identity if identity else None

        return None

    def is_identity_question(self, text: str) -> bool:
        """Detect if text contains a question about identity."""
        text = text.lower().strip()

        # Direct identity questions
        identity_questions = [
            "who am i",
            "what's my name",
            "what is my name",
            "do you know who i am",
            "do you know me",
            "do you remember me",
        ]

        if text in identity_questions:
            return True

        # More complex pattern matching
        tokens = word_tokenize(text)
        words = set(tokens)

        has_question_word = any(word in ["who", "what"] for word in words)
        has_identity_term = any(word in ["i", "me", "my", "name"] for word in words)

        return has_question_word and has_identity_term

    def get_all_topics(self, days: int = 90) -> str:
        """Get a comprehensive list of all conversation topics.

        Args:
            days: Number of days to look back (default: 90)

        Returns:
            Formatted string containing all topics and their mention counts
        """
        entities = self.retrieve_recent_entities(days=days)
        if not entities:
            return "No conversation topics found in the specified time period."

        # Sort entities by total mentions
        sorted_entities = sorted(entities, key=lambda x: x[1], reverse=True)

        # Format output using markdown
        output_parts = ["## Conversation Topics"]

        # Add top mentions with details
        for entity, total, user_count, llm_count in sorted_entities:
            source_breakdown = f"(User: {user_count}, AI: {llm_count})"
            output_parts.append(f"- **{entity}**: {total} mentions {source_breakdown}")

        # Add list of all topics
        all_topics = [entity[0] for entity in sorted_entities]
        if all_topics:
            output_parts.append("\n## All Topics Mentioned")
            output_parts.append(", ".join(all_topics))

        return "\n".join(output_parts)

    def get_memories(self) -> str:
        """Retrieve and format all stored memories."""
        entities = self.db.retrieve_recent_entities(
            days=3650
        )  # Retrieve entities from the last 10 years
        if not entities:
            return "No memories found."

        memory_parts = ["## All Stored Memories"]

        # Add identity if available
        if self.personal_identity:
            memory_parts.append(f"\n**Current User**: {self.personal_identity}")

        # Group memories by source
        user_memories = []
        llm_memories = []

        for entity, total, user_count, llm_count in entities:
            if user_count > 0:
                user_memories.append(f"- **{entity}**: {user_count} mentions")
            if llm_count > 0:
                llm_memories.append(f"- **{entity}**: {llm_count} mentions")

        if user_memories:
            memory_parts.append("\n### Things You've Mentioned")
            memory_parts.extend(user_memories)

        if llm_memories:
            memory_parts.append("\n### Things I've Mentioned")
            memory_parts.extend(llm_memories)

        # Add essence markers if available
        essence_markers = self.retrieve_essence_markers(days=3650)
        if essence_markers:
            memory_parts.append("\n### User Characteristics")
            markers_by_type = {}
            for marker_type, marker_text in essence_markers:
                markers_by_type.setdefault(marker_type, []).append(marker_text)

            for marker_type, markers in markers_by_type.items():
                memory_parts.append(f"\n**{marker_type.title()}**:")
                memory_parts.extend([f"- {marker}" for marker in markers])

        return "\n".join(memory_parts)
