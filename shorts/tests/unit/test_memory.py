from shortskit import memory as M


def test_prefs_roundtrip_and_reminders():
    assert M.load()["pending"] == []
    M.set_value("language", {"chat": "ru", "video": "ru"})
    M.set_value("platforms", ["youtube_shorts", "tiktok"])
    M.skip("panels")
    M.skip("brand")
    p = M.load()
    assert p["brand"] == {"preset": "mono"}  # default applied while pending
    line = M.reminder_line(p)
    assert line.startswith("Не заполнено:") and "панели" in line and "стиль" in line
    # reminder repeats until the item is closed
    assert M.reminder_line(M.load()) == line
    M.set_value("brand", {"preset": "viora"})  # answering closes it
    M.close_pending("panels")
    assert M.reminder_line(M.load()) == ""


def test_intake_asks_only_missing_and_summary():
    msg = M.intake_message(M.load(), "ru")
    assert "1. Кто вы" in msg and "3. Для рекламных баннеров" in msg and "7. Какой голос" in msg
    for k, v in {"language": {"chat": "ru", "video": "ru"}, "platforms": ["youtube_shorts"], "source": "site",
                 "layout": "three", "links": {"telegram": "https://t.me/x"}, "brand": {"preset": "viora"},
                 "voice": {"engine": "auto"}, "qr": False,
                 "brand.profile": {"name": "Анна", "topic": "цветы", "audience": "новички"},
                 "brand.niche": "цветы", "brand.goal": "подписки", "brand.telegram": "t.me/x", "brand.offer": "цветы по подписке",
                 "brand.style_choice": "выбери сам"}.items():
        M.set_value(k, v)
    msg = M.intake_message(M.load())
    assert msg.startswith("Беру настройки как в прошлый раз")


def test_english_reminder():
    M.set_value("language", {"chat": "en", "video": "en"})
    M.skip("links")
    assert M.reminder_line(M.load()).startswith("Not set yet: links")


def test_reset_and_behaviour_memory():
    M.remember_choice("chosen_title", "ИИ СДЕЛАЛ 8 ПУШЕК")
    M.remember_choice("rejected", "neon style")
    p = M.load()
    assert p["chosen_titles"][0]["value"] and p["rejected"][0]["value"] == "neon style"
    M.reset()
    assert M.load()["chosen_titles"] == []
