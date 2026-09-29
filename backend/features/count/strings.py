"""Every farmer-facing string in the count feature, in every language.

One place, so adding a language is editing this file rather than hunting
through detector.py, video.py and the router.

Translations are written for a farmer standing in a shed, not for a manual.
Where a phrase has no natural equivalent the meaning is kept and the wording
changed — "undercount" becomes "the number may be less than the real one",
because that is what a person would actually say.
"""
from __future__ import annotations

from core.languages import Text

# --- feature identity ---------------------------------------------------

NAME: Text = {
    "en": "Count the flock",
    "bn": "পাল গুনুন",
    "hi": "झुंड गिनें",
    "bho": "झुंड गिनीं",
    "mai": "झुंड गानू",
}

SUMMARY: Text = {
    "en": "Photo or short video of the shed; check the count by eye.",
    "bn": "শেডের ছবি বা ছোট ভিডিও; গুনতি চোখে মিলিয়ে নিন।",
    "hi": "शेड की फ़ोटो या छोटा वीडियो; गिनती आँख से जाँचें।",
    "bho": "शेड के फोटो भा छोट वीडियो; गिनती आँख से जाँची।",
    "mai": "शेडक फोटो वा छोट वीडियो; गनती आँखिसँ जाँचू।",
}

# --- prompts ------------------------------------------------------------

PROMPT: Text = {
    "en": "Photograph the shed",
    "bn": "শেডের ছবি তুলুন",
    "hi": "शेड की फ़ोटो लें",
    "bho": "शेड के फोटो लीं",
    "mai": "शेडक फोटो लिअ",
}

TAKE_PHOTO: Text = {
    "en": "Take a photo",
    "bn": "ছবি তুলুন",
    "hi": "फ़ोटो लें",
    "bho": "फोटो लीं",
    "mai": "फोटो लिअ",
}

RECORD_VIDEO: Text = {
    "en": "Record a video",
    "bn": "ভিডিও করুন",
    "hi": "वीडियो लें",
    "bho": "वीडियो लीं",
    "mai": "वीडियो लिअ",
}

VIDEO_FINDS_MORE: Text = {
    "en": "a video finds more birds than a photo",
    "bn": "ছবির চেয়ে ভিডিওতে বেশি পাখি ধরা পড়ে",
    "hi": "वीडियो में ज़्यादा पक्षी मिलते हैं",
    "bho": "वीडियो में जादा पंछी मिलेला",
    "mai": "वीडियोमे बेसी पक्षी भेटैत अछि",
}

COUNTING: Text = {
    "en": "Counting…",
    "bn": "গোনা হচ্ছে…",
    "hi": "गिन रहे हैं…",
    "bho": "गिनत बानी…",
    "mai": "गनि रहल छी…",
}

WATCHING_VIDEO: Text = {
    "en": "Watching the video… this takes a moment",
    "bn": "ভিডিও দেখা হচ্ছে… একটু সময় লাগবে",
    "hi": "वीडियो देख रहे हैं… कुछ समय लगेगा",
    "bho": "वीडियो देखत बानी… कुछ समय लागी",
    "mai": "वीडियो देखि रहल छी… किछु समय लागत",
}

BIRDS_FOUND: Text = {
    "en": "birds found",
    "bn": "পাখি পাওয়া গেছে",
    "hi": "पक्षी मिले",
    "bho": "पंछी मिलल",
    "mai": "पक्षी भेटल",
}

ENTER_CORRECT: Text = {
    "en": "Enter the correct number",
    "bn": "সঠিক সংখ্যা লিখুন",
    "hi": "सही संख्या भरें",
    "bho": "सही संख्या भरीं",
    "mai": "सही संख्या भरू",
}

RECORD_NUMBER: Text = {
    "en": "Record this number",
    "bn": "এই সংখ্যা রেকর্ড করুন",
    "hi": "दर्ज करें",
    "bho": "दर्ज करीं",
    "mai": "दर्ज करू",
}

CLEAR_LABEL: Text = {
    "en": "clear", "bn": "নিশ্চিত", "hi": "पक्का",
    "bho": "पक्का", "mai": "पक्का",
}

UNCERTAIN_LABEL: Text = {
    "en": "uncertain", "bn": "অনিশ্চিত", "hi": "हो सकता है",
    "bho": "हो सकेला", "mai": "भ' सकैत अछि",
}

FRAMES_CHECKED: Text = {
    "en": "frames checked",
    "bn": "ফ্রেম দেখা হয়েছে",
    "hi": "फ़्रेम देखे",
    "bho": "फ्रेम देखल",
    "mai": "फ्रेम देखल",
}

BEST_FRAME: Text = {
    "en": "best single frame",
    "bn": "এক ফ্রেমে সর্বোচ্চ",
    "hi": "एक फ़्रेम में सबसे ज़्यादा",
    "bho": "एक फ्रेम में सबसे जादा",
    "mai": "एक फ्रेममे सबसँ बेसी",
}

# --- quality labels -----------------------------------------------------

QUALITY: dict[str, Text] = {
    "high": {
        "en": "looks reliable", "bn": "নির্ভরযোগ্য", "hi": "भरोसेमंद",
        "bho": "भरोसा लायक", "mai": "भरोसाक योग्य",
    },
    "medium": {
        "en": "reasonable", "bn": "মোটামুটি", "hi": "ठीक-ठाक",
        "bho": "ठीक-ठाक", "mai": "ठीक-ठाक",
    },
    "low": {
        "en": "please check carefully", "bn": "ভালো করে মিলিয়ে নিন",
        "hi": "जाँच ज़रूरी", "bho": "जाँच जरूरी", "mai": "जाँच जरूरी",
    },
    "none": {
        "en": "nothing found", "bn": "কিছু পাওয়া যায়নি", "hi": "कुछ नहीं मिला",
        "bho": "कुछ ना मिलल", "mai": "किछु नहि भेटल",
    },
}

# --- notes about the count ---------------------------------------------

NOTE_NONE: Text = {
    "en": "No birds were found. Try a photo from further back, in better light.",
    "bn": "কোনো পাখি পাওয়া যায়নি। একটু পিছন থেকে, ভালো আলোয় ছবি তুলুন।",
    "hi": "कोई पक्षी नहीं मिला। थोड़ा पीछे से, अच्छी रोशनी में फ़ोटो लें।",
    "bho": "कवनो पंछी ना मिलल। थोड़ा पीछे से, बढ़िया रोशनी में फोटो लीं।",
    "mai": "कोनो पक्षी नहि भेटल। किछु पाछाँसँ, नीक इजोतमे फोटो लिअ।",
}

NOTE_CROWDED: Text = {
    "en": ("The birds are packed closely, so some behind others were probably "
           "missed. The real number is likely higher — please check and correct it."),
    "bn": ("পাখিগুলো গায়ে গায়ে আছে, তাই পিছনের কিছু বাদ পড়তে পারে। আসল সংখ্যা "
           "সম্ভবত বেশি — মিলিয়ে নিয়ে ঠিক করুন।"),
    "hi": ("पक्षी पास-पास हैं, इसलिए पीछे वाले छूट सकते हैं। असली संख्या शायद "
           "ज़्यादा है — कृपया जाँच कर सुधारें।"),
    "bho": ("पंछी पास-पास बाड़ें, त पीछे वाला छूट सकेला। असली संख्या शायद जादा "
            "बा — जाँच के सुधारीं।"),
    "mai": ("पक्षी लगिचे-लगिचे अछि, तेँ पाछाँक किछु छूटि सकैत अछि। असल संख्या "
            "बेसी भ' सकैत अछि — जाँचि क' सुधारू।"),
}

NOTE_SOME_UNCERTAIN: Text = {
    "en": "{clear} birds are clear; {rest} more are uncertain. Check the boxes and correct the number if needed.",
    "bn": "{clear}টি পাখি নিশ্চিত; আরও {rest}টি অনিশ্চিত। বাক্সগুলো দেখে সংখ্যা ঠিক করুন।",
    "hi": "{clear} पक्षी स्पष्ट हैं; {rest} पक्के नहीं। डिब्बे देखकर संख्या सुधारें।",
    "bho": "{clear} पंछी साफ बाड़ें; {rest} पक्का नइखे। डिब्बा देख के संख्या सुधारीं।",
    "mai": "{clear} पक्षी स्पष्ट अछि; {rest} पक्का नहि। बक्सा देखि क' संख्या सुधारू।",
}

NOTE_ALL_CLEAR: Text = {
    "en": "All detected birds were clear in this photo. Please still confirm the number.",
    "bn": "এই ছবিতে সব পাখি পরিষ্কার দেখা গেছে। তবুও সংখ্যাটা মিলিয়ে নিন।",
    "hi": "इस फ़ोटो में सभी पक्षी स्पष्ट थे। फिर भी संख्या की पुष्टि करें।",
    "bho": "एह फोटो में सब पंछी साफ रहलें। तबहूँ संख्या के पुष्टि करीं।",
    "mai": "एहि फोटोमे सभ पक्षी स्पष्ट छल। तइयो संख्याक पुष्टि करू।",
}

NOTE_VIDEO_BETTER: Text = {
    "en": "{counted} birds were followed across the video; the busiest single frame showed {peak}. Moving the camera found birds a photo would have missed. Please confirm the number.",
    "bn": "ভিডিওতে {counted}টি পাখি গোনা হয়েছে; এক ফ্রেমে সর্বোচ্চ {peak}টি দেখা গেছে। ক্যামেরা ঘোরানোয় এমন পাখি পাওয়া গেছে যা ছবিতে বাদ পড়ত। সংখ্যাটা মিলিয়ে নিন।",
    "hi": "वीडियो में {counted} पक्षी गिने गए; एक फ़्रेम में सबसे ज़्यादा {peak} दिखे। कैमरा घुमाने से वे पक्षी मिले जो फ़ोटो में छूट जाते। कृपया संख्या की पुष्टि करें।",
    "bho": "वीडियो में {counted} पंछी गिनल गइलें; एक फ्रेम में सबसे जादा {peak} लउकलें। कैमरा घुमावे से ऊ पंछी मिललें जे फोटो में छूट जइतें। संख्या के पुष्टि करीं।",
    "mai": "वीडियोमे {counted} पक्षी गानल गेल; एक फ्रेममे सबसँ बेसी {peak} देखाएल। कैमरा घुमेलासँ ओ पक्षी भेटल जे फोटोमे छूटि जाइत। संख्याक पुष्टि करू।",
}

NOTE_VIDEO_PLAIN: Text = {
    "en": "{counted} birds were followed across the video. Please confirm the number.",
    "bn": "ভিডিওতে {counted}টি পাখি গোনা হয়েছে। সংখ্যাটা মিলিয়ে নিন।",
    "hi": "वीडियो में {counted} पक्षी गिने गए। कृपया संख्या की पुष्टि करें।",
    "bho": "वीडियो में {counted} पंछी गिनल गइलें। संख्या के पुष्टि करीं।",
    "mai": "वीडियोमे {counted} पक्षी गानल गेल। संख्याक पुष्टि करू।",
}

NOTE_VIDEO_CUTS: Text = {
    "en": "This video jumps between separate views, so birds cannot be followed across it and this total is not reliable. Film one continuous clip, walking slowly, and count one shed at a time.",
    "bn": "এই ভিডিও আলাদা আলাদা দৃশ্যে লাফাচ্ছে, তাই পাখি অনুসরণ করা যায়নি এবং এই সংখ্যা নির্ভরযোগ্য নয়। ধীরে হেঁটে এক টানা ভিডিও করুন, একবারে একটি শেড।",
    "hi": "यह वीडियो अलग-अलग दृश्यों में कूदता है, इसलिए पक्षियों का पीछा नहीं किया जा सकता और यह संख्या भरोसेमंद नहीं है। धीरे चलकर एक ही बार में, एक शेड का वीडियो लें।",
    "bho": "ई वीडियो अलग-अलग दृश्य में कूदेला, त पंछी के पीछा ना कइल जा सके आ ई संख्या भरोसा लायक नइखे। धीरे चल के एके बेर में, एक शेड के वीडियो लीं।",
    "mai": "ई वीडियो अलग-अलग दृश्यमे कूदैत अछि, तेँ पक्षीक पाछाँ नहि जाएल जा सकैत आ ई संख्या भरोसाक नहि। मेंटरसँ चलि क' एके बेरमे, एक शेडक वीडियो लिअ।",
}

# --- errors -------------------------------------------------------------

ERR_NOT_IMAGE: Text = {
    "en": "That file is not a readable image.",
    "bn": "এই ফাইলটি ছবি নয়।",
    "hi": "यह फ़ाइल फ़ोटो नहीं है।",
    "bho": "ई फाइल फोटो नइखे।",
    "mai": "ई फाइल फोटो नहि अछि।",
}

ERR_IMAGE_BIG: Text = {
    "en": "That image is too large. Send a smaller photo.",
    "bn": "ছবিটি খুব বড়। ছোট ছবি পাঠান।",
    "hi": "फ़ोटो बहुत बड़ी है। छोटी फ़ोटो भेजें।",
    "bho": "फोटो बहुत बड़ बा। छोट फोटो भेजीं।",
    "mai": "फोटो बड़ पैघ अछि। छोट फोटो पठाउ।",
}

ERR_IMAGE_SMALL: Text = {
    "en": "That image is too small to count birds in.",
    "bn": "ছবিটি এত ছোট যে পাখি গোনা যাবে না।",
    "hi": "फ़ोटो बहुत छोटी है।",
    "bho": "फोटो बहुत छोट बा।",
    "mai": "फोटो बड़ छोट अछि।",
}

ERR_NOT_VIDEO: Text = {
    "en": "That file could not be read as a video.",
    "bn": "এই ফাইলটি ভিডিও নয়।",
    "hi": "यह फ़ाइल वीडियो नहीं है।",
    "bho": "ई फाइल वीडियो नइखे।",
    "mai": "ई फाइल वीडियो नहि अछि।",
}

ERR_VIDEO_BIG: Text = {
    "en": "That video is too large. Send a shorter clip.",
    "bn": "ভিডিওটি খুব বড়। ছোট ভিডিও পাঠান।",
    "hi": "वीडियो बहुत बड़ा है। छोटा वीडियो भेजें।",
    "bho": "वीडियो बहुत बड़ बा। छोट वीडियो भेजीं।",
    "mai": "वीडियो बड़ पैघ अछि। छोट वीडियो पठाउ।",
}

ERR_VIDEO_LONG: Text = {
    "en": "That video is {duration:.0f}s; please send one under {limit}s.",
    "bn": "ভিডিওটি {duration:.0f} সেকেন্ডের; {limit} সেকেন্ডের কম পাঠান।",
    "hi": "वीडियो {duration:.0f} सेकंड का है; {limit} सेकंड से कम भेजें।",
    "bho": "वीडियो {duration:.0f} सेकंड के बा; {limit} सेकंड से कम भेजीं।",
    "mai": "वीडियो {duration:.0f} सेकंडक अछि; {limit} सेकंडसँ कम पठाउ।",
}

ERR_VIDEO_SHORT: Text = {
    "en": "That video has too few frames to count.",
    "bn": "ভিডিওটি খুব ছোট।",
    "hi": "वीडियो बहुत छोटा है।",
    "bho": "वीडियो बहुत छोट बा।",
    "mai": "वीडियो बड़ छोट अछि।",
}

ERR_DECODE: Text = {
    "en": "The file could not be read.",
    "bn": "ফাইলটি পড়া যায়নি।",
    "hi": "फ़ाइल पढ़ी नहीं गई।",
    "bho": "फाइल पढ़ल ना गइल।",
    "mai": "फाइल पढ़ल नहि गेल।",
}

ERR_EMPTY: Text = {
    "en": "The file was empty.",
    "bn": "ফাইলটি খালি।",
    "hi": "फ़ाइल खाली है।",
    "bho": "फाइल खाली बा।",
    "mai": "फाइल खाली अछि।",
}

ERR_TOO_LARGE: Text = {
    "en": "That file is too large. Send a smaller one.",
    "bn": "ফাইলটি খুব বড়। ছোট ফাইল পাঠান।",
    "hi": "फ़ाइल बहुत बड़ी है।",
    "bho": "फाइल बहुत बड़ बा।",
    "mai": "फाइल बड़ पैघ अछि।",
}

UNAVAILABLE_PHOTO: Text = {
    "en": "Photo counting is unavailable here. Enter the number by hand.",
    "bn": "এখানে ছবি থেকে গোনা যাচ্ছে না। সংখ্যা হাতে লিখুন।",
    "hi": "फ़ोटो गिनती उपलब्ध नहीं है; संख्या हाथ से भरें।",
    "bho": "फोटो गिनती उपलब्ध नइखे; संख्या हाथ से भरीं।",
    "mai": "फोटो गनती उपलब्ध नहि; संख्या हाथसँ भरू।",
}

UNAVAILABLE_VIDEO: Text = {
    "en": "Video counting is unavailable here. Send a photo instead.",
    "bn": "এখানে ভিডিও থেকে গোনা যাচ্ছে না। ছবি পাঠান।",
    "hi": "वीडियो गिनती उपलब्ध नहीं है; फ़ोटो भेजें।",
    "bho": "वीडियो गिनती उपलब्ध नइखे; फोटो भेजीं।",
    "mai": "वीडियो गनती उपलब्ध नहि; फोटो पठाउ।",
}

RECORDED: Text = {
    "en": "Recorded {n} birds.",
    "bn": "{n}টি পাখি রেকর্ড করা হয়েছে।",
    "hi": "{n} पक्षी दर्ज किए गए।",
    "bho": "{n} पंछी दर्ज कइल गइलें।",
    "mai": "{n} पक्षी दर्ज कएल गेल।",
}

MODEL_PROPOSED: Text = {
    "en": "the model proposed {n}",
    "bn": "মডেল বলেছিল {n}",
    "hi": "मॉडल ने {n} गिना था",
    "bho": "मॉडल {n} गिनले रहे",
    "mai": "मॉडल {n} गानने छल",
}

# --- photo tips ---------------------------------------------------------

TIPS: dict[str, list[str]] = {
    "en": [
        "Stand back so the whole group fits in the frame.",
        "Take it in daylight or with the shed lights on.",
        "Hold the phone steady; a blurred photo counts badly.",
        "If the birds are packed together, photograph half the shed at a time.",
        "For a video: walk slowly in one continuous take, under a minute.",
    ],
    "bn": [
        "একটু পিছনে দাঁড়ান যাতে পুরো পাল ফ্রেমে আসে।",
        "দিনের আলোয় বা শেডের আলো জ্বালিয়ে তুলুন।",
        "ফোন স্থির রাখুন; ঝাপসা ছবিতে ঠিক গোনা যায় না।",
        "পাখি গায়ে গায়ে থাকলে অর্ধেক শেডের ছবি আলাদা করে তুলুন।",
        "ভিডিওর জন্য: ধীরে হেঁটে এক টানা, এক মিনিটের কম।",
    ],
    "hi": [
        "थोड़ा पीछे खड़े हों ताकि पूरा झुंड फ़्रेम में आए।",
        "दिन की रोशनी में या शेड की लाइट जलाकर लें।",
        "फ़ोन स्थिर रखें; धुंधली फ़ोटो सही नहीं गिनती।",
        "पक्षी पास-पास हों तो आधे-आधे शेड की दो फ़ोटो लें।",
        "वीडियो के लिए: धीरे-धीरे चलते हुए एक ही बार में, एक मिनट से कम।",
    ],
    "bho": [
        "थोड़ा पीछे खड़ा होईं ताकि पूरा झुंड फ्रेम में आवे।",
        "दिन के रोशनी में भा शेड के लाइट जरा के लीं।",
        "फोन स्थिर रखीं; धुंधला फोटो सही ना गिनाला।",
        "पंछी पास-पास होखें त आधा-आधा शेड के दू गो फोटो लीं।",
        "वीडियो खातिर: धीरे-धीरे चलत एके बेर में, एक मिनट से कम।",
    ],
    "mai": [
        "किछु पाछाँ ठाढ़ होउ जाहिसँ पूरा झुंड फ्रेममे आबय।",
        "दिनक इजोतमे वा शेडक बत्ती जरा क' लिअ।",
        "फोन स्थिर राखू; धुंधल फोटो ठीक नहि गानल जाइत।",
        "पक्षी लगिचे रहय तँ आधा-आधा शेडक दू फोटो लिअ।",
        "वीडियो लेल: मेंटरसँ चलैत एके बेरमे, एक मिनटसँ कम।",
    ],
}
