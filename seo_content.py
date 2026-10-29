"""Unique on-page copy for every tool page, plus Hindi sections.

Each tool page used to share the same steps, features and FAQ, which search engines treat as
duplicate content. PAGE_EXTRA gives every page its own text:

    about_title / about  -> short explanation written for that tool only
    tips                 -> practical tips for that tool only
    faq                  -> extra questions, shown before the shared FAQ (also goes into the FAQPage schema)
    hi_title / hi        -> a Hindi (Devanagari) section so Hindi and Hinglish searches can find the page

Everything stated here matches what the tools actually do. If a tool changes, update the text too.
"""

SITE_UPDATED = "2026-10-29"      # used for <lastmod> in the sitemap. Change it when you change page content.
LEGAL_UPDATED = "2026-10-29"

PAGE_EXTRA = {
    # ------------------------------------------------------------------ YouTube
    "/youtube-video-downloader": dict(
        about_title="Download YouTube videos as MP4 or MP3",
        about=[
            "This tool saves a regular YouTube video to your device as an MP4 file, or just its sound as an MP3. Paste the video link, press Get video, and the page shows the title, the channel, the length and every quality that video offers, from 144p up to 4K when the uploader provides it.",
            "The file is prepared on our server before it is sent to you, so a long or high-quality video takes more time than a short one. Save only videos you own, videos with a Creative Commons or public-domain licence, or videos you have permission to download.",
        ],
        tips=[
            "For a file that plays everywhere, choose 1080p or lower. Higher qualities can need a player such as VLC.",
            "Choose 360p or 480p for the fastest download and the smallest file.",
            "Choose MP3 if you only want the sound, for example a lecture or a podcast.",
            "Copy the link from the Share button or from the address bar. Short youtu.be links work too.",
        ],
        faq=[
            ("Which quality should I choose for a phone?",
             "480p or 720p is a good balance between a sharp picture and a small file on a phone. Choose 1080p if you plan to watch on a bigger screen."),
            ("Does it work on iPhone and Android?",
             "Yes. It runs in your browser, so there is nothing to install. On an iPhone, downloads usually go to the Files app."),
            ("What is the longest video I can download?",
             "Very long videos, over about three hours, may not be supported because they take too long to prepare. If a video fails, try a lower quality or audio only."),
        ],
        hi_title="YouTube Video Download Kaise Kare (यूट्यूब वीडियो डाउनलोड कैसे करें)",
        hi=[
            "यूट्यूब वीडियो डाउनलोड करने के लिए वीडियो का लिंक कॉपी करें (Share दबाकर Copy link चुनें), ऊपर वाले बॉक्स में पेस्ट करें और Get video दबाएँ। इसके बाद MP4 की क्वालिटी चुनें, या सिर्फ़ आवाज़ चाहिए तो MP3 चुनें, और Download दबाएँ।",
            "फ़ोन में कम डेटा और स्टोरेज खर्च करना हो तो 360p या 480p चुनें। सिर्फ़ वही वीडियो डाउनलोड करें जो आपके अपने हैं, जिन पर Creative Commons लाइसेंस है, या जिन्हें सेव करने की आपके पास अनुमति है।",
        ],
    ),
    "/youtube-to-mp4": dict(
        about_title="YouTube to MP4: choose your quality",
        about=[
            "MP4 works on almost every phone, tablet, laptop and TV. After you paste a link, this page lists every quality the video offers. It selects 480p or 720p first when they are available, to keep the file small, and you can change that before you press Download.",
            "Higher qualities such as 1440p and 2160p (4K) give a sharper picture, but the files are much larger and take longer to prepare, and some players need VLC to open them. Choose 1080p or lower if you want the file to open anywhere.",
        ],
        tips=[
            "Check your free storage before downloading 1080p or higher.",
            "Wi-Fi is a better choice than mobile data for large files.",
            "If a quality you want is missing, the uploader did not provide it for that video.",
            "Want only the sound? Use the YouTube to MP3 converter instead.",
        ],
        faq=[
            ("Why is 4K missing for my video?",
             "Only the qualities that the uploader provides are listed. Many videos are not available above 1080p."),
            ("Why is the MP4 file so big?",
             "File size depends on the length and the quality. A 1080p video can be several times larger than a 480p one, so choose a lower quality for a smaller file."),
            ("Will the MP4 play on my TV?",
             "Usually yes at 1080p or lower. Copy it to a USB drive or cast it from your phone. Very high qualities may not play on older TVs."),
        ],
        hi_title="YouTube Video MP4 Me Download Kaise Kare (यूट्यूब वीडियो MP4 में डाउनलोड)",
        hi=[
            "MP4 सबसे आम वीडियो फ़ॉर्मैट है, जो लगभग हर फ़ोन, कंप्यूटर और टीवी में चलता है। लिंक पेस्ट करने के बाद सूची में से क्वालिटी चुनें। छोटी फ़ाइल चाहिए तो 360p या 480p, और साफ़ तस्वीर चाहिए तो 720p या 1080p चुनें।",
            "ध्यान रखें कि ज़्यादा क्वालिटी की फ़ाइल बड़ी होती है और तैयार होने में ज़्यादा समय लेती है।",
        ],
    ),
    "/youtube-to-mp3": dict(
        about_title="Convert YouTube to MP3",
        about=[
            "This converter takes the sound from a YouTube video and saves it as a 192 kbps MP3 file. It is handy for lectures, interviews, podcasts and your own recordings.",
            "Paste the link and press Get video. The MP3 option is already selected on this page, so you only press Download. The file is made on our server and then sent to your browser, so a long video can take a little while. Convert only audio you have the right to keep.",
        ],
        tips=[
            "A 192 kbps MP3 is a good balance between sound quality and file size.",
            "Talks and lectures are small as MP3, so they are easy to keep on a phone.",
            "Rename the file after downloading if you want a cleaner title.",
            "Need the picture as well as the sound? Use the YouTube to MP4 page.",
        ],
        faq=[
            ("What quality is the MP3?",
             "Audio is saved as a 192 kbps MP3."),
            ("How long does the conversion take?",
             "A short video is usually ready quickly. A long video takes longer, because the server has to fetch and convert the audio first."),
            ("Can I convert music I don't own?",
             "Only convert audio you own or have permission to save. Music is usually protected by copyright, so see our guide on what is legal."),
        ],
        hi_title="YouTube Se MP3 Kaise Banaye (यूट्यूब वीडियो से MP3 बनाएँ)",
        hi=[
            "यूट्यूब वीडियो से सिर्फ़ आवाज़ (MP3) सेव करने के लिए लिंक कॉपी करके ऊपर पेस्ट करें और Get video दबाएँ। इस पेज पर MP3 पहले से चुना हुआ होता है, इसलिए बस Download दबाना है। फ़ाइल 192 kbps MP3 के रूप में सेव होती है।",
            "यह लेक्चर, पॉडकास्ट और अपनी रिकॉर्डिंग के लिए ठीक है। कॉपीराइट वाला गाना या दूसरी सामग्री तभी सेव करें जब आपके पास उसकी अनुमति हो।",
        ],
    ),
    # ---------------------------------------------------------------- Pinterest
    "/pindownloader": dict(
        about_title="Download Pinterest videos, images and GIFs",
        about=[
            "Pinterest does not give you a download button on most pins, and what you can save from the app is not always the biggest version. This tool reads the pin you paste and gives you the original file: the largest photo, the MP4 of a video pin, or the .gif of an animated pin.",
            "You can paste up to 20 pin links at once, one per line, and every pin gets its own Download button. Short pin.it links from the Pinterest app's Share button work too. Only individual public pins are supported, not whole boards.",
        ],
        tips=[
            "In the Pinterest app, tap Share on the pin and choose Copy link.",
            "Paste several links on separate lines to save many pins in one go.",
            "Each result is labelled Photo, Video or GIF, so you know what you are saving.",
            "Save pins for personal reference, and credit the creator if you share them.",
        ],
        faq=[
            ("Why did I get a photo and not a video?",
             "It depends on the pin. A still image downloads as a photo, a video pin as an MP4 and an animated pin as a GIF."),
            ("Why does a pin fail to load?",
             "Check that you copied the whole link and that the pin is public. Deleted or private pins can't be fetched. If it still fails, wait a minute and try again."),
        ],
        hi_title="Pinterest Video Download Kaise Kare (पिंटरेस्ट वीडियो डाउनलोड)",
        hi=[
            "पिंटरेस्ट वीडियो या फ़ोटो डाउनलोड करने के लिए पिन खोलें, Share दबाएँ और Copy link चुनें। लिंक ऊपर वाले बॉक्स में पेस्ट करें और Find media दबाएँ। वीडियो MP4 में, फ़ोटो बड़े साइज़ में और GIF असली .gif फ़ाइल के रूप में सेव होगा।",
            "एक बार में 20 लिंक तक डाल सकते हैं, और pin.it वाले छोटे लिंक भी चलते हैं। सिर्फ़ पब्लिक पिन डाउनलोड होते हैं।",
        ],
    ),
    "/pinterest-gif-downloader": dict(
        about_title="Save Pinterest GIFs as real .gif files",
        about=[
            "Paste the link of an animated pin and press Find media. If the pin is a GIF it is labelled GIF and downloads as a real .gif file, which you can send in chats, upload to a website or keep on your device.",
            "If the pin is a normal photo or video instead, you get that, and it is labelled so you know what you are saving. Short pin.it links work, and you can paste up to 20 links at once.",
        ],
        tips=[
            "Look for the GIF label on the result before you press Download.",
            "GIF files can be large, so use Wi-Fi if you are saving many.",
            "If you get a video, the pin is not a GIF. The Pinterest video downloader handles that.",
            "Credit the creator when you share someone else's GIF.",
        ],
        faq=[
            ("How can I tell if a pin is a GIF?",
             "After you press Find media, the result is labelled GIF, Video or Photo. Only pins labelled GIF download as a .gif file."),
            ("Why did I get an MP4 and not a GIF?",
             "The pin is a video, not a GIF. Some pins look animated but are videos, and those download as MP4."),
            ("Can I use the GIF in chats or on my website?",
             "A .gif file works in most chat apps and websites. Make sure you have permission before you publish someone else's GIF."),
        ],
        hi_title="Pinterest GIF Download Kaise Kare (पिंटरेस्ट GIF डाउनलोड)",
        hi=[
            "पिंटरेस्ट GIF सेव करने के लिए एनिमेटेड पिन का लिंक कॉपी करें, ऊपर पेस्ट करें और Find media दबाएँ। अगर पिन GIF है तो उस पर GIF लिखा आएगा और वह असली .gif फ़ाइल के रूप में डाउनलोड होगी।",
            "अगर पिन असल में वीडियो है तो वह MP4 के रूप में मिलेगा। किसी और की GIF पोस्ट करने से पहले उसके क्रिएटर से अनुमति ज़रूर लें।",
        ],
    ),
    # ---------------------------------------------------------------- Instagram
    "/instagram-downloader": dict(
        about_title="One tool for Reels, photos, stories and profile pictures",
        about=[
            "Paste a public post or Reel link to save the video or the photos, paste a story link to save that account's active stories, or type a username to get the profile picture. Every photo or video appears as its own card with a Download button.",
            "Nothing needs a login to Instagram, and your own account is never involved. Only public content can be downloaded. Posts from private accounts can't be saved, although profile pictures often can.",
        ],
        tips=[
            "A link ending in ?igsh=... works fine. The extra part is ignored.",
            "For a post with several photos, each picture gets its own card.",
            "Photos save as JPG files and videos as MP4.",
            "If Instagram is limiting the server, wait 5 to 10 minutes and try again.",
        ],
        faq=[
            ("Should I paste a link or a username?",
             "Use a link for a Reel, a photo or a story, and a username (or a profile link) for a profile picture. To save stories by username, use the Instagram Story Downloader."),
            ("Why does it say Instagram is limiting requests?",
             "Instagram sometimes restricts servers. Wait 5 to 10 minutes and try the same link again."),
        ],
        hi_title="Instagram Reel, Photo, DP Download Kaise Kare (इंस्टाग्राम डाउनलोडर)",
        hi=[
            "इंस्टाग्राम की रील, फ़ोटो या स्टोरी डाउनलोड करने के लिए उसका लिंक कॉपी करके ऊपर बॉक्स में पेस्ट करें और Get media दबाएँ। प्रोफ़ाइल फ़ोटो (DP) के लिए सिर्फ़ यूज़रनेम डालें। फ़ोटो JPG में और वीडियो MP4 में सेव होंगे।",
            "सिर्फ़ पब्लिक अकाउंट का कंटेंट डाउनलोड हो सकता है। किसी और का कंटेंट बिना अनुमति दोबारा पोस्ट न करें।",
        ],
    ),
    "/instagram-reels-downloader": dict(
        about_title="Download Instagram Reels as MP4",
        about=[
            "Open the Reel in Instagram, tap Share and then Copy link, and paste the link into the box above. In a few seconds you see a preview with a Download button, and the Reel is saved to your device as an MP4 file.",
            "The quality you get is the quality Instagram provides for that Reel. We do not change it or upscale it. Only public Reels can be downloaded. Save Reels you own or have permission to keep, and ask the creator before you repost their work.",
        ],
        tips=[
            "On an iPhone the file may go to the Files app first. Our iPhone guide shows how to move it to Photos.",
            "Links with ?igsh=... work. You don't need to remove anything.",
            "If no preview appears, check that the link contains /reel/ or /p/ and that the account is public.",
            "Use Wi-Fi for long Reels.",
        ],
        faq=[
            ("Is a watermark added to the Reel?",
             "No. We don't add a watermark. The file is the video Instagram provides."),
            ("Why does my Reel not load?",
             "The Reel may be from a private account, or Instagram may be limiting the server. Check that the link is complete and try again in a few minutes."),
            ("Where is the Reel saved on my phone?",
             "On Android it goes to your Downloads folder. On an iPhone it usually goes to the Files app first."),
        ],
        hi_title="Instagram Reel Download Kaise Kare (इंस्टाग्राम रील डाउनलोड कैसे करें)",
        hi=[
            "इंस्टाग्राम रील डाउनलोड करने के लिए पहले रील का लिंक कॉपी करें: रील खोलें, Share (पेपर प्लेन आइकन) दबाएँ और Copy link चुनें। फिर लिंक ऊपर वाले बॉक्स में पेस्ट करें और Get media दबाएँ। कुछ सेकंड में वीडियो का प्रीव्यू और Download बटन दिखेगा। रील MP4 फ़ाइल के रूप में सेव होगी।",
            "ध्यान रखें कि सिर्फ़ पब्लिक अकाउंट की रील डाउनलोड हो सकती है। किसी और की रील को उसकी अनुमति के बिना दोबारा पोस्ट न करें।",
        ],
    ),
    "/instagram-photo-downloader": dict(
        about_title="Save Instagram photos in full size",
        about=[
            "Paste the link of a public photo post and each picture appears as its own card with its size and a Download button. This works for single photos and for carousel posts with several pictures.",
            "You get the full-size image, not the smaller preview you see in the feed, and photos save as JPG files. Save only photos you own or have permission to keep.",
        ],
        tips=[
            "For a carousel, download only the pictures you want from the cards.",
            "Use View full size to check a picture before you download it.",
            "If a post mixes photos and videos, the videos appear as cards too and save as MP4.",
            "Posts from private accounts can't be downloaded.",
        ],
        faq=[
            ("Can I download every photo in a carousel post?",
             "Yes. Each picture in a public carousel post appears as its own card with a Download button."),
            ("Is the photo really full size?",
             "You get the largest version Instagram provides for that post, not the compressed preview shown in the feed."),
        ],
        hi_title="Instagram Photo Download Kaise Kare (इंस्टाग्राम फ़ोटो डाउनलोड)",
        hi=[
            "इंस्टाग्राम फ़ोटो डाउनलोड करने के लिए पोस्ट का लिंक कॉपी करें, ऊपर पेस्ट करें और Get media दबाएँ। अगर पोस्ट में कई फ़ोटो हैं तो हर फ़ोटो अलग कार्ड में दिखेगी, जिसके साथ उसका अपना Download बटन होगा।",
            "फ़ोटो पूरे साइज़ में JPG फ़ाइल के रूप में सेव होती है। सिर्फ़ पब्लिक पोस्ट काम करते हैं।",
        ],
    ),
    "/instagram-story-downloader": dict(
        about_title="Save Instagram stories before they disappear",
        about=[
            "Type a username or paste a story link, and every active story from that public account shows up as its own card. Photos save as JPG and videos as MP4. A story lasts 24 hours, so save it while it is live.",
            "Stories are fetched through an account used by this site, so that account may appear in the story's viewer list, but your own account is never involved. Highlights are not supported yet, and stories from private accounts can't be downloaded.",
        ],
        tips=[
            "If no story is shown, the account may have no active story right now.",
            "Check the spelling of the username. It can only contain letters, numbers, dots and underscores.",
            "A story link (instagram.com/stories/...) works too.",
            "Try again later if Instagram is limiting requests.",
        ],
        faq=[
            ("Why does it show no stories?",
             "The account may have no story at the moment, it may be private, or Instagram may be limiting the server. Check the username and try again later."),
            ("How long can I download a story?",
             "Instagram removes a story 24 hours after it is posted, so download it before then."),
        ],
        hi_title="Instagram Story Download Kaise Kare (इंस्टाग्राम स्टोरी डाउनलोड)",
        hi=[
            "इंस्टाग्राम स्टोरी 24 घंटे में गायब हो जाती है, इसलिए उसे समय रहते सेव करें। ऊपर बॉक्स में अकाउंट का यूज़रनेम या स्टोरी का लिंक डालें और Get media दबाएँ। उस अकाउंट की सभी चालू स्टोरी अलग-अलग कार्ड में दिखेंगी। फ़ोटो JPG में और वीडियो MP4 में सेव होते हैं।",
            "सिर्फ़ पब्लिक अकाउंट की स्टोरी डाउनलोड होती है, और हाइलाइट अभी सपोर्ट नहीं हैं। स्टोरी इस साइट के एक अकाउंट से निकाली जाती है, इसलिए हो सकता है वही अकाउंट व्यूअर लिस्ट में दिखे। आपका अपना अकाउंट इसमें शामिल नहीं होता।",
        ],
    ),
    "/instagram-dp-downloader": dict(
        about_title="See and save an Instagram profile picture in full size",
        about=[
            "In the Instagram app a profile picture is a small circle, and tapping it only enlarges it a little. Type a username or paste a profile link here and you get the largest version Instagram serves for that account, usually 320 pixels or bigger.",
            "Profile pictures are public, so this works for most accounts, including many private ones. The size depends on what the account uploaded, so an older account may only have a small picture. Please don't use someone's picture to impersonate or bother them.",
        ],
        tips=[
            "Type just the username, without spaces. Letters, numbers, dots and underscores only.",
            "Use View full size to open the whole picture in a new tab.",
            "A small result usually means the account only has a small picture.",
            "If the picture does not load, wait a few minutes and try again.",
        ],
        faq=[
            ("Does the account owner get a notification?",
             "Instagram does not send a notification when someone views or saves a profile picture."),
            ("Can I download the DP of a private account?",
             "Often yes, because the profile picture is public, but it can fail sometimes. The posts of a private account can't be downloaded."),
            ("Why is the DP small or blurry?",
             "We fetch the biggest version Instagram makes available. If that one is small, the account never uploaded a bigger picture."),
        ],
        hi_title="Instagram DP Download Kaise Kare (इंस्टाग्राम DP डाउनलोड)",
        hi=[
            "किसी की इंस्टाग्राम DP बड़े साइज़ में देखने और सेव करने के लिए उसका यूज़रनेम या प्रोफ़ाइल लिंक ऊपर डालें और Get media दबाएँ। आपको उस अकाउंट की सबसे बड़ी उपलब्ध फ़ोटो दिखेगी, जिसे Download दबाकर सेव कर सकते हैं।",
            "इंस्टाग्राम किसी को नोटिफ़िकेशन नहीं भेजता जब कोई उसकी प्रोफ़ाइल फ़ोटो देखता या सेव करता है। फिर भी किसी की DP का ग़लत इस्तेमाल न करें और उससे नकली अकाउंट न बनाएँ।",
        ],
    ),
    # ------------------------------------------------------------ Twitter (X)
    "/twitter-video-downloader": dict(
        about_title="Download videos from X (Twitter)",
        about=[
            "Open the tweet, copy its link from the Share button or the address bar, and paste it above. The video appears with a Download button and is saved as an MP4. If the tweet has several video sizes, you can pick the quality from the list on the card.",
            "Photos and GIFs in the same tweet show up as their own cards. Only public tweets work: protected accounts, deleted tweets and tweets marked as sensitive are not available.",
        ],
        tips=[
            "Links from both twitter.com and x.com work.",
            "Pick a smaller size if you want a lighter file.",
            "A tweet that only has text has nothing to download.",
            "Save videos for personal use, and credit the creator if you share them.",
        ],
        faq=[
            ("How do I copy a tweet link on my phone?",
             "Tap the Share icon under the tweet and choose Copy link, then paste it into the box above."),
            ("The video is in a thread. Which link do I paste?",
             "Paste the link of the specific tweet that holds the video, not the first tweet of the thread."),
        ],
        hi_title="Twitter Video Download Kaise Kare (ट्विटर वीडियो डाउनलोड)",
        hi=[
            "ट्विटर (X) का वीडियो डाउनलोड करने के लिए ट्वीट के नीचे Share दबाएँ, Copy link चुनें और लिंक ऊपर वाले बॉक्स में पेस्ट करें। Get media दबाने पर वीडियो दिखेगा, जिसे Download दबाकर MP4 के रूप में सेव कर सकते हैं।",
            "अगर ट्वीट में वीडियो के कई साइज़ हैं तो कार्ड पर से अपनी पसंद की क्वालिटी चुन सकते हैं। सिर्फ़ पब्लिक ट्वीट के वीडियो डाउनलोड होते हैं।",
        ],
    ),
    "/twitter-photo-downloader": dict(
        about_title="Save photos from tweets in original size",
        about=[
            "Paste the link of a tweet with pictures and each photo appears as its own card with its size. You download the original image, not the smaller preview that X shows in the timeline.",
            "A tweet can hold up to four photos, and you download only the ones you want. Only public tweets are supported, and a tweet without a photo has nothing to save.",
        ],
        tips=[
            "Check the size on the card to confirm you are getting the large version.",
            "For a thread, paste the link of the tweet that holds the photos.",
            "Use Wi-Fi when you save many images.",
            "Credit the photographer when you share a picture.",
        ],
        faq=[
            ("Can I save all four photos of a tweet?",
             "Yes. Each photo appears as its own card and you download them one by one."),
            ("Is the picture quality reduced?",
             "No. You get the original file, not the preview shown in the feed."),
        ],
        hi_title="Twitter Photo Download Kaise Kare (ट्विटर फ़ोटो डाउनलोड)",
        hi=[
            "ट्वीट की फ़ोटो असली साइज़ में सेव करने के लिए ट्वीट का लिंक कॉपी करके ऊपर पेस्ट करें और Get media दबाएँ। ट्वीट की हर फ़ोटो अलग कार्ड में दिखेगी, जिसके साथ उसका साइज़ भी लिखा होगा।",
            "जो फ़ोटो चाहिए उसका Download बटन दबाएँ। किसी और की फ़ोटो शेयर करने से पहले उसके मालिक से अनुमति लें और क्रेडिट दें।",
        ],
    ),
    "/twitter-gif-downloader": dict(
        about_title="Save GIFs from tweets as looping MP4 files",
        about=[
            "X stores its GIFs as short looping videos, so that is what you download: an MP4 that plays on a loop in most apps and players.",
            "Paste the tweet link, press Get media and look for the card with the GIF label. Only public tweets work, and a tweet without a GIF has nothing to save.",
        ],
        tips=[
            "Most apps and players loop the MP4 automatically.",
            "If an app only accepts .gif files, convert the MP4 with a separate converter after downloading.",
            "The GIF label tells you which card is the GIF and which is a normal video.",
            "Credit the creator when you share a GIF that is not yours.",
        ],
        faq=[
            ("Why is my GIF an MP4 file?",
             "That is how X stores GIFs. The MP4 is the original file and it loops in most players."),
            ("Can I turn the MP4 into a .gif file?",
             "This site saves the original MP4. If an app needs a .gif, you can convert the MP4 with a separate converter."),
        ],
        hi_title="Twitter GIF Download Kaise Kare (ट्विटर GIF डाउनलोड)",
        hi=[
            "ट्विटर (X) पर GIF असल में छोटे लूप होने वाले वीडियो होते हैं, इसलिए वे MP4 फ़ाइल के रूप में डाउनलोड होती हैं। ट्वीट का लिंक कॉपी करें, ऊपर पेस्ट करें और Get media दबाएँ। जिस कार्ड पर GIF लिखा हो, उसका Download दबाएँ।",
            "ज़्यादातर ऐप और प्लेयर में यह फ़ाइल अपने आप बार-बार चलती है।",
        ],
    ),
}

HOME_EXTRA = dict(
    about_title="A free downloader for Instagram, YouTube, Pinterest and X",
    about=[
        "MaxDownloader puts the tools people use most in one place: an Instagram Reels, photo, story and profile picture downloader, a YouTube video and MP3 downloader, a Pinterest video, image and GIF downloader, and a Twitter (X) video, photo and GIF downloader. Paste a link above and we open the right tool for you.",
        "Everything runs in your browser on a phone or a computer, with no sign-up. Only download content you own or have permission to save, and read our guides if you are not sure what is allowed.",
    ],
    hi_title="Instagram Reel, DP, Story aur Pinterest Video Free Me Download Kare (मुफ़्त डाउनलोडर)",
    hi=[
        "MaxDownloader पर इंस्टाग्राम रील, फ़ोटो, स्टोरी और DP, यूट्यूब वीडियो और MP3, पिंटरेस्ट वीडियो, इमेज और GIF, और ट्विटर (X) के वीडियो मुफ़्त में डाउनलोड कर सकते हैं। बस लिंक कॉपी करें, ऊपर बॉक्स में पेस्ट करें और Download दबाएँ। न कोई ऐप इंस्टॉल करना है, न लॉगिन करना है।",
        "सिर्फ़ वही कंटेंट डाउनलोड करें जो आपका अपना हो या जिसे सेव करने की आपके पास अनुमति हो।",
    ],
)
