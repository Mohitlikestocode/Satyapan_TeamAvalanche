"""Round 2 templates for tools/make_scam_corpus.py: more Hinglish and Hindi genuine messages (the model confused ordinary bank, office and offer
messages with scams) and more scam wordings in the same languages. Different wording from round 1 so the model learns the category, not the sentence."""
from __future__ import annotations

GENUINE_EXTRA2: dict[str, dict[str, list[str]]] = {
    "bank_upi_debit": {
        "hinglish": ["{shop} ko {amt} UPI se bheje gaye, aapke account XX{n}{n} se. Ye aapne nahi kiya to bank ki helpline par turant batayein.",
                     "Aapke account XX{n}{n} me {amt} jama hue, {person} ki taraf se. Balance app me dekh sakte hain.",
                     "UPI debit: {amt} {shop} ko, ref {ref}. Dispute ke liye bank ki official app kholein."],
        "hi": ["{amt} यूपीआई से {shop} को भेजे गए, आपके खाते XX{n}{n} से। आपने नहीं किया तो बैंक हेल्पलाइन पर तुरंत बताएँ।"],
        "en": ["UPI debit of {amt} to {shop}, ref {ref}. Open your bank's official app to raise a dispute if this was not you."],
    },
    "security_awareness": {
        "hinglish": ["Bank kabhi aapse OTP, PIN ya password nahi poochta. Agar koi phone par maange to turant call kaat dein aur 1930 par report karein.",
                     "Savdhan rahein: anjaan numbers se aaye links par click na karein aur kisi ko screen share na karein.",
                     "Tip: apna UPI PIN sirf paisa bhejte waqt daalein, paise lene ke liye kabhi nahi."],
        "hi": ["सावधान रहें: बैंक कभी ओटीपी या पासवर्ड नहीं पूछता। फ़ोन पर कोई माँगे तो कॉल काटकर 1930 पर बताएँ।",
               "सुझाव: यूपीआई पिन सिर्फ़ पैसे भेजते समय डालें, पैसे पाने के लिए कभी नहीं।"],
        "en": ["Tip: enter your UPI PIN only when you send money, never to receive it. If someone says otherwise, it is a scam.",
               "Beware of calls asking you to install screen-sharing apps. Your bank will never do this."],
    },
    "office_chat": {
        "hinglish": ["Sab log kal ki review meeting ke liye apna status update bhej do. Vendor ke payment ki approval Neha ke paas hai.",
                     "Salary slip aur reimbursement ka form HR ko friday tak bhej dena, payment agle hafte process hoga.",
                     "Client ne invoice approve kar diya hai, payment is hafte ke end tak aa jayega."],
        "hi": ["सब लोग कल की समीक्षा बैठक के लिए अपनी स्थिति भेज दें। विक्रेता के भुगतान की मंज़ूरी नेहा के पास है।"],
        "en": ["Please send your status updates before tomorrow's review. Neha holds the approval for the vendor payment.",
               "The client approved the invoice, so the payment should reach us by the end of the week."],
    },
    "telecom_plan": {
        "hinglish": ["Aapka mobile plan kal expire ho raha hai. Recharge ke liye apne operator ke official app ya store ka use karein.",
                     "Aapka data pack 80% use ho gaya hai. Details operator ke app me dekhein."],
        "hi": ["आपका मोबाइल प्लान कल समाप्त हो रहा है। रिचार्ज के लिए ऑपरेटर के आधिकारिक ऐप या स्टोर का उपयोग करें।"],
        "en": ["Your mobile plan ends tomorrow. Please recharge using your operator's official app or store."],
    },
    "investment_genuine": {
        "hinglish": ["Aapka SIP is mahine ki 5 tarikh ko process ho gaya, units folio me add ho gaye. Statement app me available hai.",
                     "Aapka fixed deposit {date} ko mature ho raha hai. Renew karne ke liye branch ya app dekhein."],
        "hi": ["आपका एसआईपी इस महीने की 5 तारीख को पूरा हो गया, यूनिट फोलियो में जुड़ गईं। स्टेटमेंट ऐप में है।"],
        "en": ["Your SIP for this month was processed on the 5th and the units are added to your folio. The statement is in the app."],
    },
    "retail_offer": {
        "hinglish": ["Festival sale! Sabhi products par 25% tak ki chhoot, 5 November tak. Apne nazdiki showroom me aayein. Shartein laagu.",
                     "Hamare naye store ka udghatan Sunday ko hai, pehle 100 customers ko free gift."],
        "hi": ["त्योहार सेल! सभी उत्पादों पर 25% तक की छूट, 5 नवंबर तक। अपने नज़दीकी शोरूम में आएँ। शर्तें लागू।"],
        "en": ["Festival sale: up to 25% off everything until 5 November at your nearest showroom. Terms apply."],
    },
    "family_money_benign": {
        "hinglish": ["Bhai kal rent ka hissa bhej dena, main landlord ko ek saath de dunga. Receipt screenshot bhej dunga.",
                     "Papa fee ka payment kal kar dena, college ki receipt portal par daal di hai, maine check kar liya hai."],
        "hi": ["भैया कल किराए का हिस्सा भेज देना, मैं मकान मालिक को एक साथ दे दूँगा। रसीद का स्क्रीनशॉट भेज दूँगा।"],
        "en": ["Please send your share of the rent tomorrow and I will pay the landlord in one go. I will share the receipt screenshot."],
    },
    "shipping_genuine": {
        "hinglish": ["Aapka order dispatch ho gaya hai, kal tak pahunch jayega. Tracking details app me hain.",
                     "Aapka parcel delivery ke liye nikal chuka hai. Delivery agent ko OTP sirf saaman haath me aane par dein."],
        "hi": ["आपका ऑर्डर भेज दिया गया है, कल तक पहुँच जाएगा। ट्रैकिंग का विवरण ऐप में है।"],
        "en": ["Your order has been dispatched and will arrive tomorrow. Tracking details are in the app."],
    },
}
SCAM_EXTRA2: dict[str, dict[str, list[str]]] = {
    "digital_arrest": {
        "hinglish": ["{auth} ki taraf se call hai. Aapke naam se aaya parcel drugs ke saath pakda gaya. Video call chalu rakho, kisi ko batana nahi aur case band karwane ke liye {amt} abhi bhejo.",
                     "Aapka SIM illegal kaam me use hua hai. Aap abhi digital arrest me hain. Camera on rakho aur {amt} verification account me transfer karo."],
        "hi": ["{auth} की ओर से कॉल है। आपके नाम का पार्सल ड्रग्स के साथ पकड़ा गया है। वीडियो कॉल चालू रखें, किसी को न बताएँ और केस बंद करवाने के लिए अभी {amt} भेजें।"],
        "en": ["This is {auth}. A parcel in your name was caught with drugs. Keep the video call on, tell nobody, and send {amt} now to close the case."],
    },
    "electricity_cut": {
        "hinglish": ["Bijli vibhag: aapka bill baaki hai, aaj raat tak connection band kar diya jayega. Abhi {phone} par call karke app se payment karein.",
                     "Aapke meter ka bill update nahi hua, {time} supply cut hogi. Is number par turant sampark karein: {phone}."],
        "hi": ["बिजली विभाग: आपका बिल बाकी है, आज रात तक कनेक्शन बंद कर दिया जाएगा। अभी {phone} पर कॉल करके ऐप से भुगतान करें।"],
        "en": ["Electricity board: your bill is overdue and the connection will be cut tonight. Call {phone} now and pay through the app we send."],
    },
    "relative_emergency": {
        "hinglish": ["Mummy mera phone toot gaya, dost ke number se likh raha hu. Abhi {amt} bhej do, bahut emergency hai, papa ko mat batana.",
                     "Beta main chacha bol raha hu, accident ho gaya, hospital me hu. {amt} turant {upi} par bhejo."],
        "hi": ["मम्मी मेरा फ़ोन टूट गया है, दोस्त के नंबर से लिख रहा हूँ। अभी {amt} भेज दो, बहुत इमरजेंसी है, पापा को मत बताना।"],
        "en": ["Mum my phone broke and I am using a friend's number. Send {amt} right now, it is an emergency, please do not tell dad."],
    },
    "fake_support": {
        "hinglish": ["Customer care se bol raha hu. Refund ke liye AnyDesk install karke code bataiye, uske baad apna UPI PIN daalna hoga.",
                     "Aapke gas connection ki subsidy atki hai. Madad ke liye AnyDesk app dalo aur screen par aaya code hamare agent ko do."],
        "hi": ["कस्टमर केयर से बोल रहा हूँ। रिफंड के लिए एनीडेस्क इंस्टॉल करके कोड बताइए, फिर अपना यूपीआई पिन डालना होगा।"],
        "en": ["Customer care speaking. For your refund install AnyDesk, tell me the code, then enter your UPI PIN."],
    },
    "fake_loan_app": {
        "hinglish": ["Bina CIBIL ke {amt} tak ka loan. App download karo, contacts allow karo aur pehle {fee} insurance fees bhejo, tabhi loan approve hoga.",
                     "Loan approve ho gaya, bas {fee} processing fee {upi} par bhej do, paisa 10 minute me account me."],
        "hi": ["बिना सिबिल के {amt} तक का लोन। ऐप डाउनलोड करें, कॉन्टैक्ट्स की अनुमति दें और पहले {fee} बीमा शुल्क भेजें, तभी लोन पास होगा।"],
        "en": ["Loan of up to {amt} with no CIBIL check. Download the app, allow contacts and pay {fee} insurance first, then the loan is approved."],
    },
    "crypto_double": {
        "hinglish": ["Crypto platform par {amt} lagao, {days} din me paisa double. Nikalne ke liye pehle {pct}% tax account manager ko bhejna padega.",
                     "USDT trading group join karo, members ne {days} din me {pct}x kamaya. {amt} deposit karo aur kabhi bhi withdraw karo."],
        "hi": ["क्रिप्टो प्लेटफ़ॉर्म पर {amt} लगाएँ, {days} दिन में पैसा दोगुना। निकासी के लिए पहले {pct}% टैक्स भेजना होगा।"],
        "en": ["Invest {amt} on our crypto platform and double it in {days} days. To withdraw you first pay {pct}% tax to the account manager."],
    },
    "fake_payment_proof": {
        "hinglish": ["Sir payment ho gaya hai, screenshot bhej raha hu. Bank server slow hai isliye message nahi aaya. Maal aaj hi dispatch kar do.",
                     "{amt} bhej diye hain, screenshot dekh lijiye. Kuch der me aapke account me dikh jayega, order abhi bhej do."],
        "hi": ["सर भुगतान हो गया है, स्क्रीनशॉट भेज रहा हूँ। बैंक सर्वर धीमा है इसलिए संदेश नहीं आया। माल आज ही भेज दें।"],
        "en": ["Sir the payment is done and the screenshot is attached. My bank server is slow so you may not get the message. Please dispatch today."],
    },
    "job_task": {
        "en": ["Work from home and earn {amt} a day by liking videos. Join our Telegram group and pay the {fee} registration fee to begin, it is refundable."],
        "hi": ["घर बैठे वीडियो लाइक करके रोज़ {amt} कमाएँ। टेलीग्राम ग्रुप से जुड़ें और शुरू करने के लिए {fee} पंजीकरण शुल्क दें, यह वापस मिलेगा।"],
    },
}
