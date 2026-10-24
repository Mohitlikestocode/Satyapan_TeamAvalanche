"""More templates for tools/make_scam_corpus.py: extra scam wordings and many more genuine kinds (awareness notices, UPI debit alerts,
office chat, plan expiry, SIP, offers, family chat). Same slot syntax. All invented."""
from __future__ import annotations

SCAM_EXTRA: dict[str, dict[str, list[str]]] = {
    "digital_arrest": {
        "en": ["Hello, I am calling from {auth}. We found drugs in a courier sent from your Aadhaar. Do not tell anyone, stay on video, and deposit {amt} in the verification account or officers will reach your home.",
               "A criminal case under the money laundering act is filed on your number. You are not allowed to leave this call. Transfer {amt} for case settlement."],
        "hi": ["मैं {auth} से बोल रहा हूँ। आपके आधार से भेजे गए कूरियर में ड्रग्स मिले हैं। किसी को न बताएँ, वीडियो पर बने रहें और सत्यापन खाते में {amt} जमा करें वरना अधिकारी आपके घर पहुँचेंगे।"],
        "hinglish": ["Main {auth} se bol raha hu. Aapke Aadhaar se bheje courier me drugs mile hain. Kisi ko mat batana, video par rahiye aur verification account me {amt} jama karo warna officers ghar aa jayenge.",
                     "Aapke number par criminal case darj hua hai. Is call se hatna mana hai. Case settle karne ke liye {amt} transfer karein."],
    },
    "electricity_cut": {
        "en": ["Dear consumer, your electricity connection will be disconnected {time} as your previous month bill is not updated. Call the officer on {phone} immediately.",
               "Power department notice: bill unpaid, meter will be removed {time}. Pay at once using the link {link} or call {phone}."],
        "hi": ["प्रिय उपभोक्ता, पिछले महीने का बिल अपडेट न होने से आपका बिजली कनेक्शन {time} काट दिया जाएगा। तुरंत {phone} पर अधिकारी से बात करें।",
               "बिजली विभाग सूचना: बिल बकाया है, {time} मीटर हटा दिया जाएगा। अभी {link} से भुगतान करें।"],
        "hinglish": ["Dear consumer, pichle mahine ka bill update na hone se aapka bijli connection {time} kat diya jayega. Turant {phone} par officer se baat karein."],
    },
    "fake_support": {
        "en": ["Your gas connection subsidy is on hold. For help install the AnyDesk app and tell our agent the code shown on your screen.",
               "Bank security team: suspicious activity found. To secure your funds install TeamViewer and give us the ID shown."],
        "hi": ["आपके गैस कनेक्शन की सब्सिडी रुकी हुई है। मदद के लिए एनीडेस्क ऐप डालें और स्क्रीन पर दिख रहा कोड एजेंट को बताएँ।",
               "बैंक सुरक्षा टीम: संदिग्ध गतिविधि मिली है। पैसे सुरक्षित करने के लिए टीमव्यूअर इंस्टॉल करें और आईडी बताएँ।"],
        "hinglish": ["Gas subsidy ruki hui hai. Madad ke liye AnyDesk app install karein aur screen par dikh raha code hamare agent ko batayein."],
    },
    "fake_payment_proof": {
        "en": ["Sir I have already paid, see the screenshot. Because of network slow you did not get the message. Please send the goods today, my money is deducted.",
               "Payment of {amt} done, screenshot attached. It shows pending for some time. Kindly dispatch the order now."],
        "hi": ["सर मैंने भुगतान कर दिया है, स्क्रीनशॉट देखिए। नेटवर्क धीमा होने से आपको संदेश नहीं आया। कृपया माल आज ही भेज दें, मेरे पैसे कट गए हैं।"],
        "hinglish": ["Bhaiya maine payment kar diya, ye dekho screenshot. Network slow hai isliye message nahi aaya. Maal aaj hi bhej do, mere paise kat gaye."],
    },
    "relative_emergency": {
        "en": ["Uncle here, my phone is dead and I am using a friend's number. I had an accident and need {amt} for the hospital. Send it now to {upi}.",
               "Bro I am stuck at the police station, phone confiscated, using someone's number. Send {amt} to {upi} immediately, do not call anyone."],
        "hi": ["चाचा बोल रहा हूँ, मेरा फ़ोन बंद है और दोस्त के नंबर से लिख रहा हूँ। एक्सीडेंट हो गया है, अस्पताल के लिए तुरंत {amt} भेजो।",
               "मैं थाने में फँसा हूँ, फ़ोन ज़ब्त है। {amt} अभी इसी खाते में भेजो, किसी को फ़ोन मत करना।"],
        "hinglish": ["Papa mera accident ho gaya hai, abhi hospital me hu. Phone toot gaya, ye naya number hai. {amt} abhi isi number par bhej do, baad me samjhaunga.",
                     "Bhai police station me fasa hu, phone le liya hai. {amt} turant bhejo, kisi ko call mat karna."],
    },
    "fake_loan_app": {
        "en": ["Instant loan up to {amt} with no CIBIL check. Download the app, allow contacts access, pay {fee} insurance fees first and the loan is approved."],
        "hi": ["सिबिल की जाँच के बिना {amt} तक का तुरंत लोन। ऐप डाउनलोड करें, कॉन्टैक्ट्स की अनुमति दें, पहले {fee} बीमा शुल्क भरें, लोन पास हो जाएगा।"],
        "hinglish": ["Bina CIBIL check ke {amt} tak instant loan. App download karo, contacts access allow karo, pehle {fee} insurance fees pay karo to loan approve hoga."],
    },
    "courier_redelivery": {
        "en": ["Your courier is undelivered. To update the address pay {small} at {link}.", "Parcel on hold, address incomplete. Pay {small} redelivery fee here: {link}."],
        "hi": ["आपका कूरियर वितरित नहीं हुआ। पता अपडेट करने के लिए {link} पर {small} शुल्क दें।"],
        "hinglish": ["Aapka courier undelivered hai. Address update karne ke liye {small} ki charge is link par pay karo: {link}"],
    },
    "job_task": {
        "hi": ["घर बैठे वीडियो लाइक करके रोज़ {amt} कमाएँ। टेलीग्राम पर जुड़ें। पंजीकरण शुल्क {fee}। पहला भुगतान तुरंत।",
               "ऑनलाइन टास्क करो और रोज़ {amt} पाओ। शुरू करने से पहले {fee} जमा कराना होगा, बाद में वापस मिलेगा।"],
        "hinglish": ["Ghar baithe videos like karke roz {amt} kamao. Telegram par judo. Registration fee {fee}, pehla payment turant.",
                     "Online task karo aur roz {amt} pao. Shuru karne se pehle {fee} deposit karna hoga, baad me wapas milega."],
    },
    "fake_app": {
        "en": ["Download our trading app and earn {amt} profit on day one. For withdrawal you must first deposit {pct}% income tax."],
        "hi": ["हमारा ट्रेडिंग ऐप डाउनलोड करें और पहले दिन {amt} का मुनाफ़ा पाएँ। निकासी के लिए पहले {pct} प्रतिशत इनकम टैक्स जमा करना होगा।"],
        "hinglish": ["Hamara trading app download karo aur pehle din {amt} profit pao. Nikalne ke liye pehle {pct}% income tax jama karna hoga."],
    },
    "rental_deposit": {
        "en": ["Flat available at {amt} per month near the metro, owner is out of station. Pay the token amount {fee} to {upi} to book, keys by courier."],
        "hi": ["मेट्रो के पास फ्लैट {amt} महीने पर उपलब्ध है, मालिक शहर से बाहर हैं। बुक करने के लिए {upi} पर टोकन राशि {fee} भेजें, चाबी कूरियर से आएगी।"],
        "hinglish": ["Metro ke paas flat {amt} per month par available hai, owner bahar hain. Book karne ke liye {upi} par token {fee} bhejiye, chaabi courier se aayegi."],
    },
    "invoice_change": {
        "hi": ["महोदय, हमारा बैंक खाता बदल गया है। इस महीने का बिल नए खाते {acct} में जमा करें। पुराना खाता बंद है।"],
        "hinglish": ["Sir hamara bank account change ho gaya hai. Is mahine ka bill naye account {acct} me jama karein, purana account band hai."],
    },
    "sextortion_threat": {
        "en": ["I recorded our video call. Pay {amt} to this UPI ID within 2 hours or I will send it to everyone in your contact list."],
        "hi": ["मैंने हमारी वीडियो कॉल रिकॉर्ड कर ली है। 2 घंटे में इस यूपीआई आईडी पर {amt} भेजो वरना सबको भेज दूँगा।"],
        "hinglish": ["Maine hamari video call record kar li hai. 2 ghante me is UPI ID par {amt} bhejo warna sabko bhej dunga."],
    },
}

GENUINE_EXTRA: dict[str, dict[str, list[str]]] = {
    "security_awareness": {
        "en": ["Be careful: your bank will never ask for your OTP, PIN or CVV. If anyone asks on a call, hang up and call the bank on the number on your card.",
               "Fraud alert from {bank}: do not click on links in unknown messages and do not install apps shared by strangers. Report to 1930.",
               "Reminder: Satyapan, banks and the police never ask you to transfer money to a safe account."],
        "hi": ["सावधान: बैंक कभी आपसे ओटीपी, पिन या सीवीवी नहीं माँगता। कोई कॉल पर माँगे तो कॉल काटें और कार्ड के पीछे के नंबर पर बैंक को फ़ोन करें।",
               "साइबर सुरक्षा सुझाव: अनजान लिंक पर क्लिक न करें और अजनबी के भेजे ऐप इंस्टॉल न करें। धोखाधड़ी हो तो 1930 पर बताएँ।"],
        "hinglish": ["Dhyan rahe: bank kabhi OTP, PIN ya CVV nahi maangta. Koi call par maange to call kaat do aur bank ko card ke peeche wale number par phone karo.",
                     "Cyber suraksha tip: anjaan link par click na karein aur kisi ke bheje app install na karein. Fraud ho to 1930 par batayein."],
    },
    "bank_upi_debit": {
        "en": ["{amt} debited from your account XX{n}{n} via UPI to {shop}. If you did not do this, call the number on the back of your card.",
               "UPI payment of {amt} to {shop} successful. Ref no {ref}. -{bankshort}", "{amt} received from {person} in your account XX{n}{n} via UPI. -{bankshort}"],
        "hi": ["आपके खाते XX{n}{n} से यूपीआई द्वारा {shop} को {amt} कट गए। यह आप नहीं थे तो कार्ड के पीछे के नंबर पर कॉल करें।",
               "यूपीआई से {shop} को {amt} का भुगतान सफल रहा। संदर्भ संख्या {ref}। -{bankshort}"],
        "hinglish": ["{amt} aapke account XX{n}{n} se UPI se kate gaye, {shop} ko. Aapne nahi kiya to card ke peeche wale number par call karein.",
                     "{person} se aapke account me {amt} UPI se aaye. -{bankshort}", "UPI se {shop} ko {amt} ka payment safal raha. Ref {ref}."],
    },
    "office_chat": {
        "en": ["Team, tomorrow's meeting is at 11. Please share your monthly report. Rahul will check the vendor payment status.",
               "Can you send me the invoice copy and the PO number? I will clear the payment after approval.",
               "Reminder: submit your reimbursement claims by Friday. Finance will process them next week."],
        "hi": ["टीम, कल की बैठक 11 बजे है। सब अपनी मासिक रिपोर्ट भेज दें। वेंडर भुगतान की स्थिति राहुल देखेंगे।",
               "कृपया इनवॉइस की कॉपी और पीओ नंबर भेज दीजिए। मंज़ूरी के बाद भुगतान कर दूँगा।"],
        "hinglish": ["Team, kal ki meeting 11 baje hai. Sab apna monthly report share kar do. Vendor payment ka status Rahul dekh raha hai.",
                     "Invoice ki copy aur PO number bhej do, approval ke baad payment kar dunga."],
    },
    "plan_expiry_genuine": {
        "en": ["Your internet plan expires tomorrow. To recharge, use the company's official app or a nearby retailer.", "Your DTH balance is low. Recharge from the official app to avoid interruption."],
        "hi": ["आपका इंटरनेट प्लान कल खत्म हो रहा है। रिचार्ज के लिए कंपनी के आधिकारिक ऐप या नज़दीकी दुकान का उपयोग करें।"],
        "hinglish": ["Aapka internet plan kal khatam ho raha hai. Naya recharge karne ke liye company ke official app ya nazdiki retailer ka use karein.",
                     "Aapka DTH balance kam hai. Official app se recharge karein."],
    },
    "sip_genuine": {
        "hi": ["आपका {amt} का एसआईपी इस महीने की 5 तारीख को पूरा हो गया। यूनिट आपके फोलियो में जमा हैं। विवरण ऐप में देखें।"],
        "hinglish": ["Aapka {amt} ka SIP is mahine ki 5 tarikh ko execute ho gaya. Units aapke folio me jama hain. Details app me dekhein."],
        "en": ["Your SIP of {amt} was executed on the 5th. Units are credited to your folio. See details in the app."],
    },
    "retail_offer": {
        "en": ["Diwali offer! Up to 30% off on all clothes till 31 October. Visit your nearest store. Terms apply.", "Weekend sale at our showroom, free gift on purchases above {amt}. Come visit us."],
        "hi": ["दिवाली ऑफ़र! सभी कपड़ों पर 30% तक की छूट, 31 अक्टूबर तक। अपने नज़दीकी स्टोर पर आएँ। शर्तें लागू।"],
        "hinglish": ["Diwali offer! Sabhi kapdon par 30% tak ki chhoot, 31 October tak. Apne nazdiki store par aayein. Sharten laagu."],
    },
    "family_chat": {
        "en": ["Mom, I reached the hostel. Will call after dinner. Please don't worry.", "Dad, the exam went well. I will send the fee receipt once the college uploads it.",
               "Bhaiya, please send me the recipe you made last week. And are you coming for Diwali?"],
        "hi": ["माँ, मैं हॉस्टल पहुँच गया। खाने के बाद फ़ोन करूँगा। चिंता मत करना।", "पापा, परीक्षा अच्छी गई। कॉलेज रसीद अपलोड करेगा तो भेज दूँगा।"],
        "hinglish": ["Mummy main hostel pahunch gaya. Khane ke baad call karunga, chinta mat karna.", "Bhaiya wo recipe bhej do jo pichle hafte banayi thi. Aur Diwali par aa rahe ho na?"],
    },
    "shop_staff_chat": {
        "en": ["Sir your order of rice and dal is ready, you can pick it up after 5 or I will send it with the delivery boy. Pay on delivery.",
               "Madam, your tailoring is ready. Please collect it tomorrow and pay the balance at the shop."],
        "hi": ["सर, आपका चावल और दाल का सामान तैयार है, 5 बजे के बाद ले जाइए या डिलीवरी बॉय से भिजवा देता हूँ। भुगतान डिलीवरी पर कीजिए।"],
        "hinglish": ["Sir aapka chawal aur dal ka order ready hai, 5 baje ke baad le jaiye ya delivery boy se bhej dunga. Payment delivery par kar dena."],
    },
    "rent_genuine": {
        "en": ["Hi, I am the landlord. Rent for November is due on the 1st as usual, same account as before. Thanks!", "Your society maintenance of {amt} is due by the 10th. Pay at the society office or through the official app."],
        "hi": ["नमस्ते, मकान मालिक बोल रहा हूँ। नवंबर का किराया हमेशा की तरह 1 तारीख को देय है, खाता वही पुराना। धन्यवाद!"],
        "hinglish": ["Hi, main landlord hu. November ka rent hamesha ki tarah 1 tarikh ko dena hai, same account me. Thanks!"],
    },
    "health_genuine": {
        "en": ["Your lab report is ready. You can collect it from the centre or download it from the official site with your registered mobile number.", "Reminder: your vaccination slot is tomorrow at 10 AM at the primary health centre."],
        "hi": ["आपकी लैब रिपोर्ट तैयार है। केंद्र से ले सकते हैं या पंजीकृत मोबाइल नंबर से आधिकारिक साइट से डाउनलोड करें।"],
        "hinglish": ["Aapki lab report ready hai. Centre se le sakte hain ya registered mobile number se official site se download karein."],
    },
    "ecommerce_genuine": {
        "en": ["Your return is picked up. The refund of {amt} will be credited to the original payment method in 5 to 7 working days.", "Your {courier} order #{ref} is delayed by a day due to weather. We are sorry for the inconvenience."],
        "hi": ["आपका रिटर्न उठा लिया गया है। {amt} का रिफंड 5 से 7 कार्य दिवसों में मूल भुगतान माध्यम में आ जाएगा।"],
        "hinglish": ["Aapka return pick ho gaya hai. {amt} ka refund 5 se 7 working days me original payment method me aa jayega."],
    },
    "emergency_benign": {
        "en": ["Granny is in the hospital for a check-up, nothing serious. Come by in the evening if you can.", "Please call me when you are free, I need your advice on the loan paperwork from the bank branch."],
        "hi": ["दादी जाँच के लिए अस्पताल में हैं, कुछ गंभीर नहीं है। हो सके तो शाम को आ जाना।"],
        "hinglish": ["Dadi check-up ke liye hospital me hain, kuch serious nahi hai. Ho sake to shaam ko aa jana.", "Free ho to call karna, bank branch ke loan ke paperwork par salah chahiye."],
    },
}
