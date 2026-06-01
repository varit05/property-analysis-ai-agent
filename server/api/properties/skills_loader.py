"""
Skill loading — loads YAML skill definitions from the skills directory.

Each YAML file defines a skill with:
  - name: The skill's unique name
  - description: What the skill does
  - inputs: The parameters the skill accepts
  - function: The Python function path (module.function_name)
  - output: What the skill returns
"""

import importlib
import inspect
import logging
from pathlib import Path
from types import FunctionType

import yaml

from server.core.config import settings

logger = logging.getLogger(__name__)


class Skill:
    """A skill loaded from a YAML definition file."""

    def __init__(
        self,
        name: str,
        description: str,
        inputs: dict,
        function_path: str,
        output: dict,
    ):
        self.name = name
        self.description = description
        self.inputs = inputs
        self.function_path = function_path
        self.output = output
        self._fn = None

    def get_function(self):
        """Lazy-import the skill's function."""
        if self._fn is not None:
            return self._fn
        module_path, _, func_name = self.function_path.rpartition(".")
        module = importlib.import_module(module_path)
        self._fn = getattr(module, func_name)
        return self._fn

    async def call(self, **kwargs) -> FunctionType:
        """Call the skill function with the given arguments."""
        fn = self.get_function()
        if inspect.iscoroutinefunction(fn):
            return await fn(**kwargs)
        return fn(**kwargs)

    def to_dict(self) -> dict:
        """Serialise for inclusion in LLM prompts."""
        return {
            "name": self.name,
            "description": self.description,
            "inputs": self.inputs,
            "output": self.output,
        }


def load_skills(skills_dir: str | None = None) -> dict[str, Skill]:
    """Load all YAML skill files from the skills directory.

    Returns a dict mapping skill name → Skill instance.
    """
    if skills_dir is None:
        skills_dir = settings.SKILLS_DIR

    skills_dir_path = Path(skills_dir)
    if not skills_dir_path.is_absolute():
        # Resolve relative to the project root
        skills_dir_path = Path.cwd() / skills_dir_path

    skills = {}
    if not skills_dir_path.exists():
        logger.warning("Skills directory not found: %s", skills_dir_path)
        return skills

    for yaml_file in sorted(skills_dir_path.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            skill = Skill(
                name=data["name"],
                description=data["description"],
                inputs=data.get("inputs", {}),
                function_path=data["function"],
                output=data.get("output", {}),
            )
            skills[skill.name] = skill
            logger.debug("Loaded skill: %s from %s", skill.name, yaml_file.name)
        except Exception as e:
            logger.exception("Failed to load skill from %s: %s", yaml_file, e)

    logger.info("Loaded %d skills from %s", len(skills), skills_dir_path)
    return skills
