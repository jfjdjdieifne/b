# -*- coding: utf-8 -*-
import json
import os
import logging
from datetime import datetime
from openrouter_client import OpenRouterClient
from config import Config


class LearningManager:
    """
    مسؤول عن تعليم البوت مفاهيم واستراتيجيات ومصطلحات التداول من النصوص.
    """

    def __init__(self, file_path="data/learned_knowledge.json"):
        self.logger = logging.getLogger("LearningManager")
        self.ai = OpenRouterClient()
        self.file_path = file_path
        Config.ensure_data_dir()
        self.knowledge = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                self.logger.error(f"Failed to load knowledge file: {e}")
        return []

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.knowledge, f, ensure_ascii=False, indent=2)

    def learn_text(self, text):
        prompt = f"""
You are a trading knowledge extraction engine.

The user will provide text about trading.
Your task:
1. Understand every term in trading context.
2. Extract all important knowledge.
3. Classify each extracted item into one of:
   - concept
   - strategy
   - rule
   - glossary_term
   - risk_management
   - entry_condition
   - exit_condition
   - pattern
4. Return JSON array only.

For each item return:
{{
  "type": "...",
  "name": "...",
  "definition": "...",
  "conditions": [],
  "tags": [],
  "examples": [],
  "notes": "...",
  "confidence": 0-100
}}

Text:
{text}
"""
        result = self.ai.query_json(prompt, max_tokens=3000)

        if isinstance(result, list):
            for item in result:
                item["source_text"] = text
                item["created_at"] = str(datetime.now())
                self.knowledge.append(item)
            self._save()
            return {
                "saved": len(result),
                "items": result
            }

        return {
            "saved": 0,
            "items": [],
            "raw": result
        }

    def search(self, keyword):
        keyword = keyword.lower()
        found = []
        for item in self.knowledge:
            raw = json.dumps(item, ensure_ascii=False).lower()
            if keyword in raw:
                found.append(item)
        return found

    def all_knowledge(self):
        return self.knowledge[-50:]
