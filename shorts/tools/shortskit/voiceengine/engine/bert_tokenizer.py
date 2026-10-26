# Vendored from silero-stress (MIT License, (c) Silero Team): custom_tokenizers/bert_tokenizer.py
# Modified only in SimpleBertTokenizer.__init__ to load bundled vocab/config files.
import os
import re
import json
import collections
import unicodedata

class BasicTokenizer:   
    def __init__(self, never_split=None, tokenize_chinese_chars=True):
        self.never_split = set(never_split) if never_split else set()
        self.tokenize_chinese_chars = tokenize_chinese_chars
    
    def tokenize(self, text, never_split=None):
        never_split = self.never_split.union(set(never_split)) if never_split else self.never_split
        text = self._clean_text(text)
        
        if self.tokenize_chinese_chars:
            text = self._tokenize_chinese_chars(text)
        
        orig_tokens = text.strip().split()
        split_tokens = []
        for token in orig_tokens:
            if token in never_split:
                split_tokens.append(token)
            else:
                split_tokens.extend(self._run_split_on_punc(token, never_split))
        
        output_tokens = " ".join(split_tokens).split()
        return output_tokens

    def _clean_text(self, text):
        output = []
        for char in text:
            cp = ord(char)
            if cp == 0 or cp == 0xfffd or self._is_control(char):
                continue
            if self._is_whitespace(char):
                output.append(" ")
            else:
                output.append(char)
        return "".join(output)
    
    def _is_control(self, char):
        if char == "\t" or char == "\n" or char == "\r":
            return False
        cat = unicodedata.category(char)
        if cat.startswith("C"):
            return True
        return False
    
    def _is_whitespace(self, char):
        if char == " " or char == "\t" or char == "\n" or char == "\r":
            return True
        cat = unicodedata.category(char)
        if cat == "Zs":
            return True
        return False
    
    def _tokenize_chinese_chars(self, text):
        output = []
        for char in text:
            cp = ord(char)
            if self._is_chinese_char(cp):
                output.append(" ")
                output.append(char)
                output.append(" ")
            else:
                output.append(char)
        return "".join(output)
    
    def _is_chinese_char(self, cp):
        if ((cp >= 0x4E00 and cp <= 0x9FFF) or
            (cp >= 0x3400 and cp <= 0x4DBF) or
            (cp >= 0x20000 and cp <= 0x2A6DF) or
            (cp >= 0x2A700 and cp <= 0x2B73F) or
            (cp >= 0x2B740 and cp <= 0x2B81F) or
            (cp >= 0x2B820 and cp <= 0x2CEAF) or
            (cp >= 0xF900 and cp <= 0xFAFF) or
            (cp >= 0x2F800 and cp <= 0x2FA1F)):
            return True
        return False
    
    def _run_split_on_punc(self, token, never_split=None):
        never_split = never_split or set()
        if token in never_split:
            return [token]
        
        chars = list(token)
        i = 0
        start_new_word = True
        output = []
        while i < len(chars):
            char = chars[i]
            if self._is_punctuation(char):
                output.append([char])
                start_new_word = True
            else:
                if start_new_word:
                    output.append([])
                start_new_word = False
                output[-1].append(char)
            i += 1
        
        return ["".join(x) for x in output]
    
    def _is_punctuation(self, char):
        cp = ord(char)
        if ((cp >= 33 and cp <= 47) or (cp >= 58 and cp <= 64) or
            (cp >= 91 and cp <= 96) or (cp >= 123 and cp <= 126)):
            return True
        
        cat = unicodedata.category(char)
        if cat.startswith("P"):
            return True
        
        return False


class WordpieceTokenizer:
    def __init__(self, vocab, unk_token="[UNK]", max_input_chars_per_word=100):
        self.vocab = vocab
        self.unk_token = unk_token
        self.max_input_chars_per_word = max_input_chars_per_word
    
    def tokenize(self, text):
        output_tokens = []
        for token in text.split():
            chars = list(token)
            if len(chars) > self.max_input_chars_per_word:
                output_tokens.append(self.unk_token)
                continue
            
            is_bad = False
            start = 0
            sub_tokens = []
            while start < len(chars):
                end = len(chars)
                cur_substr = None
                while start < end:
                    substr = "".join(chars[start:end])
                    if start > 0:
                        substr = "##" + substr
                    if substr in self.vocab:
                        cur_substr = substr
                        break
                    end -= 1
                
                if cur_substr is None:
                    is_bad = True
                    break
                
                sub_tokens.append(cur_substr)
                start = end
            
            if is_bad:
                output_tokens.append(self.unk_token)
            else:
                output_tokens.extend(sub_tokens)
        
        return output_tokens


class SimpleBertTokenizer:
    def __init__(self, vocab_tokens, config):
        never_split = config.get("never_split", []) or []
        self.never_split = set(never_split)
        self.tokenize_chinese_chars = config.get("tokenize_chinese_chars", True)
        self.unk_token = config.get("unk", "[UNK]")
        self.sep_token = config.get("sep", "[SEP]")
        self.pad_token = config.get("pad", "[PAD]")
        self.cls_token = config.get("cls", "[CLS]")
        self.mask_token = config.get("mask", "[MASK]")
        self.vocab = collections.OrderedDict((t, i) for i, t in enumerate(vocab_tokens))
        self.unk_token_id = self.vocab.get(self.unk_token)
        self.sep_token_id = self.vocab.get(self.sep_token)
        self.pad_token_id = self.vocab.get(self.pad_token)
        self.cls_token_id = self.vocab.get(self.cls_token)
        self.homo_start_id = self.vocab.get('[HOMO]')
        self.homo_end_id = self.vocab.get('[/HOMO]')
        self.basic_tokenizer = BasicTokenizer(never_split=self.never_split,
                                              tokenize_chinese_chars=self.tokenize_chinese_chars)
        self.wordpiece_tokenizer = WordpieceTokenizer(vocab=self.vocab, unk_token=self.unk_token,
                                                      max_input_chars_per_word=config.get("max_chars", 100))

    def tokenize(self, text):
        tokens = self.basic_tokenizer.tokenize(text, never_split=self.never_split)
        return self.wordpiece_tokenizer.tokenize(" ".join(tokens))

    def encode(self, text):
        tokens = [self.cls_token] + self.tokenize(text) + [self.sep_token]
        return [self.vocab.get(t, self.unk_token_id) for t in tokens]

    __call__ = encode
