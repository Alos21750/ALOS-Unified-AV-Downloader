import re

from uav_downloader.subtitles import domain


def test_versions_and_authored_phrase_inventory_are_explicit():
    assert domain.DOMAIN_VERSION
    assert domain.DOMAIN_ENGINE_VERSION == domain.DOMAIN_VERSION
    assert domain.GLOSSARY_VERSION
    # These floors guard against accidentally shipping a truncated authored
    # corpus without coupling the test to one exact inventory size.
    assert domain.PHRASE_COUNT >= 800
    assert domain.NONLEXICAL_COUNT >= 60
    assert len(domain._EXPLICIT_DOMAIN_EXPANSION) >= 200
    assert len(domain._SPECIALIZED_DOMAIN_EXPANSION) >= 100


def test_authored_inventory_has_no_normalized_duplicates_or_conflicts():
    phrase_keys = [domain.normalize_cue(row[0]) for row in domain._PHRASES]
    sound_keys = [domain.normalize_cue(row[0]) for row in domain._NONLEXICAL]

    assert len(phrase_keys) == len(set(phrase_keys)) == domain.PHRASE_COUNT
    assert len(sound_keys) == len(set(sound_keys)) == domain.NONLEXICAL_COUNT
    assert set(phrase_keys).isdisjoint(sound_keys)


def test_every_authored_output_is_nonempty_single_cue_text_without_protocol_artifacts():
    timestamp = re.compile(r"\b\d{1,2}:\d{2}:\d{2}[,.]\d{3}\b")
    forbidden_markers = (
        "-->",
        "__JABLE",
        "JABLE_CUE",
        "[[",
        "]]",
        "<<<",
        ">>>",
        "<|",
        "|>",
        "<extra_id_",
        "</s>",
        "<unk>",
        "\u241e",
    )

    for inventory_name, rows in (
        ("phrases", domain._PHRASES),
        ("nonlexical", domain._NONLEXICAL),
    ):
        for source, english, taiwan in rows:
            assert source.strip(), (inventory_name, source)
            assert not any(character in source for character in "\r\n\t"), (
                inventory_name,
                source,
            )

            for language, output in (("en", english), ("zh-TW", taiwan)):
                assert isinstance(output, str), (inventory_name, source, language)
                assert output and output == output.strip(), (inventory_name, source, language)
                assert not any(character in output for character in "\r\n\t"), (
                    inventory_name,
                    source,
                    language,
                )
                assert timestamp.search(output) is None, (inventory_name, source, language)
                assert not any(marker in output for marker in forbidden_markers), (
                    inventory_name,
                    source,
                    language,
                )
                if inventory_name == "phrases":
                    assert domain.exact_translation(source, "ja", language) == output
                else:
                    assert domain.normalize_nonlexical(source, language) == output


def test_high_risk_negative_outputs_keep_explicit_negation_in_both_languages():
    english_negators = ("don't", "doesn't", "isn't", "can't", "not ", " no ")
    taiwan_negators = ("不", "沒", "別", "無")

    for _, negative in domain._NEGATION_SOURCE_PAIRS:
        english = domain.exact_translation(negative, "ja", "en").lower()
        taiwan = domain.exact_translation(negative, "ja", "zh-TW")
        assert any(token in f" {english} " for token in english_negators), (negative, english)
        assert any(token in taiwan for token in taiwan_negators), (negative, taiwan)


def test_normalize_cue_handles_nfkc_whitespace_and_japanese_punctuation():
    assert domain.normalize_cue("  「やめて　！！」\r\n") == "やめて"
    assert domain.normalize_cue("続けて……") == "続けて"
    assert domain.normalize_cue("ｷｽして。") == "キスして"


def test_question_mark_is_normalized_without_promoting_ambiguous_bare_cues():
    assert domain.normalize_cue("大丈夫。") == "大丈夫"
    assert domain.normalize_cue("大丈夫？") == "大丈夫?"
    assert domain.exact_translation("大丈夫。", "ja", "en") is None
    assert domain.exact_translation("大丈夫？", "ja-JP", "en") is None

    # The grammatical question remains safe and accepts either question-mark
    # width after normalization.
    assert domain.exact_translation("大丈夫ですか？", "ja-JP", "en") == (
        "Is everything okay?"
    )
    assert domain.exact_translation("大丈夫ですか?", "ja", "zh-TW") == "都還好嗎？"


def test_exact_lookup_covers_common_control_and_comfort_phrases():
    assert domain.exact_translation("　やめて！ ", "Japanese", "en") == "Stop."
    assert domain.exact_translation("やめないで", "ja", "zh-TW") == "不要停。"
    assert domain.exact_translation("続けて…", "ja", "zh-Hant") == "繼續。"
    assert domain.exact_translation("もっと速く", "ja", "en") == "Faster."
    assert domain.exact_translation("もっとゆっくり", "ja", "zh") == "再慢一點。"
    assert domain.exact_translation("もっと優しく", "ja", "zh-TW") == "再溫柔一點。"
    assert domain.exact_translation("気持ちよくない", "ja", "en") == "It doesn't feel good."


def test_exact_lookup_covers_adult_context_without_changing_intent():
    assert domain.exact_translation("入れないで", "ja", "en") == "Don't put it in."
    assert domain.exact_translation("中に出さないで", "ja", "zh-TW") == "不要射在裡面。"
    assert domain.exact_translation("触らないで", "ja", "en") == "Don't touch."
    assert domain.exact_translation("声を出さないで", "ja", "zh-TW") == "不要出聲。"


def test_every_declared_negation_pair_is_exact_distinct_and_never_substring_matched():
    assert len(domain._NEGATION_SOURCE_PAIRS) >= 40

    for affirmative, negative in domain._NEGATION_SOURCE_PAIRS:
        affirmative_en = domain.exact_translation(affirmative, "ja", "en")
        negative_en = domain.exact_translation(negative, "ja", "en")
        affirmative_zh = domain.exact_translation(affirmative, "ja", "zh-TW")
        negative_zh = domain.exact_translation(negative, "ja", "zh-TW")

        assert affirmative_en is not None, affirmative
        assert negative_en is not None, negative
        assert affirmative_zh is not None, affirmative
        assert negative_zh is not None, negative
        assert affirmative_en != negative_en, (affirmative, negative)
        assert affirmative_zh != negative_zh, (affirmative, negative)

        # Neither member may leak into a longer unknown cue.
        assert domain.exact_translation(f"前文{affirmative}後文", "ja", "en") is None
        assert domain.exact_translation(f"前文{negative}後文", "ja", "en") is None


def test_declared_question_pairs_never_depend_on_punctuation_alone():
    assert len(domain._QUESTION_SOURCE_PAIRS) >= 8

    for statement, question in domain._QUESTION_SOURCE_PAIRS:
        statement_key = domain.normalize_cue(statement)
        question_key = domain.normalize_cue(question)

        assert question_key.endswith("?"), question
        assert statement_key != question_key.removesuffix("?"), (statement, question)

        statement_en = domain.exact_translation(statement, "ja", "en")
        question_en = domain.exact_translation(question, "ja", "en")
        statement_zh = domain.exact_translation(statement, "ja", "zh-TW")
        question_zh = domain.exact_translation(question, "ja", "zh-TW")

        assert statement_en is not None, statement
        assert question_en is not None, question
        assert statement_zh is not None, statement
        assert question_zh is not None, question
        assert statement_en != question_en, (statement, question)
        assert statement_zh != question_zh, (statement, question)
        assert domain.exact_translation(question.replace("?", "？"), "ja", "en") == question_en


def test_entire_authored_inventory_has_no_punctuation_only_question_pair():
    keys = {domain.normalize_cue(row[0]) for row in domain._PHRASES}
    for question in (key for key in keys if key.endswith("?")):
        assert question.removesuffix("?") not in keys, question


def test_complete_grammatical_questions_have_authored_golden_translations():
    expected = {
        "大丈夫ですか?": ("Is everything okay?", "都還好嗎？"),
        "してもいい?": ("May I?", "可以嗎？"),
        "本当にいいの?": ("Is it really okay?", "真的可以嗎？"),
        "どこがいい?": ("Where feels good?", "哪裡舒服？"),
        "カメラは回っていますか?": ("Is the camera rolling?", "攝影機有在拍嗎？"),
        "音声は入っていますか?": ("Is audio being captured?", "有錄到聲音嗎？"),
        "何時に始まりますか?": ("What time does it start?", "幾點開始？"),
    }

    for source, (english, taiwan) in expected.items():
        assert domain.exact_translation(source, "ja", "en") == english
        assert domain.exact_translation(source, "ja", "zh-TW") == taiwan


def test_longer_or_partial_cues_never_fuzzy_match():
    assert domain.exact_translation("本当にやめないで", "ja", "en") is None
    assert domain.exact_translation("やめ", "ja", "en") is None
    assert domain.exact_translation("気持ちいいわけじゃない", "ja", "en") is None
    assert domain.exact_translation("カメラを見てから始めて", "ja", "en") is None
    assert domain.exact_translation("お願いだからやめて", "ja", "en") is None


def test_ambiguous_bare_cues_are_deliberately_left_to_the_local_model():
    for cue in (
        "大丈夫",
        "大丈夫?",
        "大丈夫です",
        "平気",
        "平気?",
        "平気ですか?",
        "大丈夫じゃない",
        "いい?",
        "いいですか?",
        "痛い?",
        "痛くない?",
        "苦しい?",
        "苦しくない?",
        "気持ちいい?",
        "気持ちよくない?",
        "怖くない?",
        "ここ?",
        "ここがいい?",
        "ここはだめ?",
        "出して",
        "吸って",
        "吸わないで",
        "口に出して",
        "顔に出して",
        "顔にかけて",
        "胸に出して",
        "お腹に出して",
        "外に出して",
        "そとに出して",
        "外に出すよ",
        "奥まで",
        "奥がいい",
        "引いて",
        "引かないで",
        "解いて",
        "疲れてる",
        "いく",
        "行く",
        "いきそう",
        "好き",
        "きつい",
        "濡れてる",
        "そこ",
        "もういいよ",
        "もういいです",
        "よろしくお願いします",
        "よろしくお願いいたします",
        "すみません",
        "失礼します",
        "違います",
        "準備できた?",
        "カメラ回ってる?",
        "もう撮ってる?",
        "音声入ってる?",
        "ピント合ってる?",
    ):
        assert domain.exact_translation(cue, "ja", "en") is None, cue
        assert domain.exact_translation(cue, "ja", "zh-TW") is None, cue


def test_explicit_disambiguated_cues_keep_their_authored_meaning():
    expected = {
        "私の顔に射精して": ("Ejaculate on my face.", "射精在我臉上。"),
        "私の口に入れて": ("Put it in my mouth.", "放進我嘴裡。"),
        "私の口に入れないで": (
            "Don't put it in my mouth.",
            "不要放進我嘴裡。",
        ),
        "息ができない": ("I can't breathe.", "我沒辦法呼吸。"),
        "手を後ろに回して": (
            "Put your hands behind you.",
            "把手放到身後。",
        ),
        "声を抑えられない": (
            "I can't keep my voice down.",
            "我壓不住聲音。",
        ),
        "乳首を吸って": (
            "Suck my nipples.",
            "吸我的乳頭。",
        ),
    }

    for source, (english, taiwan) in expected.items():
        assert domain.exact_translation(source, "ja", "en") == english
        assert domain.exact_translation(source, "ja", "zh-TW") == taiwan


def test_expanded_safety_privacy_production_and_asr_cues_have_golden_translations():
    expected = {
        "今すぐ全部の動きを止めて": (
            "Stop all movement right now.",
            "現在立刻停止所有動作。",
        ),
        "この行為には同意していません": (
            "I do not consent to this act.",
            "我不同意這個行為。",
        ),
        "救急車を呼んでください": (
            "Please call an ambulance.",
            "請叫救護車。",
        ),
        "救急車呼んで": (
            "Call an ambulance.",
            "叫救護車。",
        ),
        "コンドームが破れた": (
            "The condom broke.",
            "保險套破了。",
        ),
        "まだ射精しないで": (
            "Do not ejaculate yet.",
            "還不要射精。",
        ),
        "口と鼻を同時に塞がないで": (
            "Do not cover the mouth and nose at the same time.",
            "不要同時摀住口鼻。",
        ),
        "コンドームなしの行為には同意しません": (
            "I do not consent to sex without a condom.",
            "我不同意無套性行為。",
        ),
        "撮影場所が分からないようにして": (
            "Make sure the filming location cannot be identified.",
            "不要讓人辨認出拍攝地點。",
        ),
        "この映像は販売しないで": (
            "Do not sell this footage.",
            "不要販售這段影像。",
        ),
        "マイクが服に擦れています": (
            "The microphone is rubbing against the clothing.",
            "麥克風摩擦到衣服了。",
        ),
        "いきがくるしい": (
            "I am having trouble breathing.",
            "我呼吸有困難。",
        ),
        "どういをてっかいします": (
            "I withdraw my consent.",
            "我撤回同意。",
        ),
    }

    for source, (english, taiwan) in expected.items():
        assert domain.exact_translation(source, "ja", "en") == english
        assert domain.exact_translation(source, "ja", "zh-TW") == taiwan


def test_unknown_or_unsupported_cues_return_none_for_local_model():
    assert domain.exact_translation("今日はいい天気ですね", "ja", "en") is None
    assert domain.exact_translation("やめて", "en", "zh-TW") is None
    assert domain.exact_translation("やめて", "ja", "fr") is None
    assert domain.exact_translation("", "ja", "en") is None


def test_nonlexical_cues_are_exact_and_do_not_use_broad_sound_heuristics():
    assert domain.normalize_nonlexical("（喘ぎ声）", "en") == "[moaning]"
    assert domain.normalize_nonlexical("[キス音]", "zh-TW") == "（接吻聲）"
    assert domain.exact_translation(" はぁはぁ… ", "ja", "en") == "[panting]"
    assert domain.exact_translation("んっ", "ja", "zh-TW") == "嗯。"
    assert domain.normalize_nonlexical("[衣擦れ]", "en") == "[clothes rustling]"
    assert domain.normalize_nonlexical("[カメラのシャッター音]", "zh-TW") == "（相機快門聲）"
    assert domain.normalize_nonlexical("[すすり泣き]", "en") == "[sobbing]"
    assert domain.normalize_nonlexical("[リップ音]", "en") == "[lip-smacking sounds]"
    assert domain.normalize_nonlexical("[リップ音]", "zh-TW") == "（嘴唇聲）"
    assert domain.normalize_nonlexical("あああああ", "en") is None
    assert domain.normalize_nonlexical("前文[喘ぎ]後文", "en") is None


def test_exact_lookup_covers_protection_privacy_and_production_cues():
    assert domain.exact_translation("ゴムなしはだめ", "ja", "zh-TW") == "沒戴保險套不行。"
    assert domain.exact_translation("コンドームを外さないで", "ja", "en") == (
        "Don't remove the condom."
    )
    assert domain.exact_translation("顔は映さないで", "ja", "zh-TW") == "不要拍到臉。"
    assert domain.exact_translation("本名は言わないで", "ja", "en") == (
        "Don't say the real name."
    )
    assert domain.exact_translation("カメラは回っていますか？", "ja", "zh-TW") == (
        "攝影機有在拍嗎？"
    )
    assert domain.exact_translation("もう一回お願いします", "ja", "en") == (
        "One more time, please."
    )


def test_exact_lookup_covers_body_reactions_emotion_and_politeness():
    assert domain.exact_translation("息できない", "ja", "zh-TW") == "我沒辦法呼吸。"
    assert domain.exact_translation("吐きそう", "ja", "en") == (
        "I feel like I'm going to be sick."
    )
    assert domain.exact_translation("怖くない", "ja", "zh-TW") == "我不怕。"
    assert domain.exact_translation("やめてください", "ja", "en") == "Please stop."
    assert domain.exact_translation("何かあったら言って", "ja", "zh-TW") == (
        "有任何狀況就跟我說。"
    )


def test_exact_lookup_covers_pose_clothing_and_direction_cues():
    assert domain.exact_translation("仰向けになって", "ja", "zh-TW") == "仰躺。"
    assert domain.exact_translation("もっと足を開いて", "ja", "en") == (
        "Spread your legs wider."
    )
    assert domain.exact_translation("腰を動かさないで", "ja", "zh-TW") == "腰不要動。"
    assert domain.exact_translation("シャツは脱がないで", "ja", "en") == (
        "Don't take off your shirt."
    )
    assert domain.exact_translation("もう少し右", "ja", "zh-TW") == "再往右一點。"
    assert domain.exact_translation("顔を上げて", "ja", "en") == "Raise your head."
    assert domain.exact_translation("顔を下げて", "ja", "zh-TW") == "低下頭。"


def test_high_confidence_asr_spellings_have_the_same_trusted_meaning():
    assert domain.exact_translation("きもちいい", "ja", "en") == domain.exact_translation(
        "気持ちいい", "ja", "en"
    )
    assert domain.exact_translation("ちょっとまって", "ja", "zh-TW") == (
        domain.exact_translation("ちょっと待って", "ja", "zh-TW")
    )
    assert domain.exact_translation("さわらないで", "ja", "en") == (
        domain.exact_translation("触らないで", "ja", "en")
    )
    assert domain.exact_translation("なかに出さないで", "ja", "zh-TW") == (
        domain.exact_translation("中に出さないで", "ja", "zh-TW")
    )


def test_common_dialogue_groups_are_substantive_and_have_golden_translations():
    assert 50 <= len(domain._COMMON_DIALOGUE) <= 100
    assert len(domain._COMMON_GREETINGS) >= 20
    assert len(domain._COMMON_COURTESY) >= 20
    assert len(domain._COMMON_UNDERSTANDING) >= 20
    assert len(domain._COMMON_DIRECTIONS) >= 20

    expected = {
        "これはテストです": ("This is a test.", "這是測試。"),
        "こんにちは": ("Hello.", "你好。"),
        "こんばんは": ("Good evening.", "晚上好。"),
        "ありがとう": ("Thank you.", "謝謝。"),
        "ありがとうございます": ("Thank you very much.", "非常感謝。"),
        "遅れてすみません": ("Sorry I'm late.", "抱歉我遲到了。"),
        "ごめんなさい": ("I'm sorry.", "對不起。"),
        "お願いします": ("Please.", "拜託了。"),
        "わかりました": ("I understand.", "我明白了。"),
        "わかりません": ("I don't understand.", "我不明白。"),
        "知らない": ("I don't know.", "我不知道。"),
        "ここに座ってください": ("Please sit here.", "請坐在這裡。"),
        "何時に始まりますか?": ("What time does it start?", "幾點開始？"),
    }
    for source, (english, taiwan) in expected.items():
        assert domain.exact_translation(source, "ja", "en") == english
        assert domain.exact_translation(source, "ja", "zh-TW") == taiwan


def test_common_dialogue_still_never_uses_substring_matching():
    assert domain.exact_translation("こんにちは皆さん", "ja", "en") is None
    assert domain.exact_translation("本当にありがとうございますね", "ja", "zh-TW") is None
    assert domain.exact_translation("わかりましたと言いました", "ja", "en") is None


def test_taiwan_postprocess_is_conservative_and_preserves_layout():
    source = "這個視頻在文件夾裏面。\n網絡軟件的質量很好。"
    assert domain.postprocess_taiwan(source) == (
        "這個影片在資料夾裡面。\n網路軟體的品質很好。"
    )
    assert domain.postprocess_taiwan(
        "不要拿掉安全套 。攝像機正在錄像 ！"
    ) == "不要拿掉保險套。攝影機正在錄影！"
    assert domain.postprocess_taiwan(
        "第二天下午,我們會在海灘旅館 談一項新計畫。"
    ) == "第二天下午，我們會在海灘旅館談一項新計畫。"
    assert domain.postprocess_taiwan(
        "版本 2.5.34, build 12"
    ) == "版本 2.5.34, build 12"


def test_postprocess_only_handles_text_and_leaves_srt_metadata_untouched():
    index = "17"
    timestamp = "00:01:02,300 --> 00:01:04,900"
    translated = domain.postprocess_taiwan("視頻在這裏")
    assert index == "17"
    assert timestamp == "00:01:02,300 --> 00:01:04,900"
    assert translated == "影片在這裡"


def test_english_postprocess_fixes_model_casing_without_rewriting_words():
    assert domain.postprocess_english(
        "i'm going to check the equipment. i think it's ready."
    ) == "I'm going to check the equipment. I think it's ready."
    assert domain.postprocess_english(
        '"please wait."\n(i will be right back.)'
    ) == '"Please wait."\n(I will be right back.)'
    assert domain.postprocess_english(
        "eBay and iPhone are already correctly styled."
    ) == "eBay and iPhone are already correctly styled."
