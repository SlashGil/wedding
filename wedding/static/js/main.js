// --- LightGallery ---
document.addEventListener('DOMContentLoaded', function() {
    lightGallery(document.getElementById('photo-gallery'), {
        selector: '.gallery-item',
        download: false,
        getCaptionFromTitleOrAlt: false
    });

    const loadMoreBtn = document.getElementById('load-more-photos');
    if (loadMoreBtn) {
        const buttonText = loadMoreBtn.querySelector('span');
        loadMoreBtn.addEventListener('click', function() {
            const hiddenItems = document.querySelectorAll('.gallery-item.hidden-initially');
            if (buttonText.getAttribute('data-i18n') === 'view_more') {
                hiddenItems.forEach(item => {
                    item.style.display = 'block';
                });
                buttonText.setAttribute('data-i18n', 'view_less');
            } else {
                hiddenItems.forEach(item => {
                    item.style.display = 'none';
                });
                buttonText.setAttribute('data-i18n', 'view_more');
                document.getElementById('photo-gallery').scrollIntoView({ behavior: 'smooth' });
            }
            setLang(currentLang);
        });
    }
});

// --- Internationalization (i18n) ---
const translations = {
    en: {
        subtitle: "Are getting married!",
        welcome: "Welcome",
        reserved: "We've reserved",
        seats: "seat(s) in your honor",
        and: "and",
        kids_seats: "seat(s) for kids",
        when_where: "When & Where",
        ceremony: "Church Ceremony",
        ceremony_date: "July 11, 2026 at 1:45 PM",
        map: "Open church in Google Maps",
        reception: "Reception Venue",
        cocktails: "Cocktails start at",
        cocktails_time: "3:30 PM",
        map_venue: "Open venue in Google Maps",
        countdown: "The Countdown",
        days: "Days", hours: "Hours", minutes: "Minutes", seconds: "Seconds",
        dress_code: "Dress Code",
        formal: window.weddingConfig.dressCodeEn,
        women: "👗 Women", men: "👔 Men",
        w_rule1: "Long evening gowns, elegant midi dresses, or elevated cocktail dresses.",
        w_rule2: "Recommended palette: champagne, dusty rose, muted gold, and soft green.",
        w_rule3: "Please avoid white or ivory tones reserved for the bride.",
        forbidden_colors_title: "Forbidden Colors:",
        color_red: "Red",
        color_beige: "Beige",
        color_petroleum_blue: "Petrol Blue",
        color_navy_blue: "Navy Blue",
        hotels: "Suggested Hotels",
        view_map: "View on Map",
        photos: "Our Photos",
        registry: "Gift Registry",
        gift_msg: "Your presence is the greatest gift of all. However, if you wish to honor us with a gift, we are registered at the following stores.",
        thank_you: "Thank you,",
        rsvp_yes: "We are so happy you will celebrate with us!",
        rsvp_adults: "Reserved adults:",
        rsvp_kids: "Kids attending:",
        rsvp_no: "Thank you for letting us know. We will miss you on our special day.",
        rsvp_update: "If you need to update your response, please use your invitation link again.",
        rsvp_title: "RSVP",
        form_name: "Name",
        form_attend: "Will you be joining us?",
        form_yes: "Yes, I'll be there!",
        form_no: "Sadly, I can't make it",
        form_adults: "Number of Adults",
        form_max_adults: "Maximum allowed for this invite:",
        form_kids: "Number of Kids",
        form_max_kids: "Kids allowed on this invite:",
        form_diet: "Dietary Restrictions",
        form_submit: "Submit RSVP",
        m_rule1: "Dark suit with tie or bow tie, or a tuxedo for a more formal look.",
        m_rule2: "Recommended colors: black, navy, charcoal, and deep green.",
        m_rule3: "Polished dress shoes are preferred for the ceremony and reception.",
        music_play: "Play Music",
        music_pause: "Pause Music",
        view_more: "View More",
        view_less: "View Less",
        bank_details_btn: "Bank Transfer",
        bank_transfer_title: "Bank Transfer",
        bank_transfer_msg: "You can make an electronic transfer using the following details:",
        copy_clabe: "Copy CLABE",
        clabe_copied: "CLABE Copied! ✓"
    },
    es: {
        subtitle: "¡Nos casamos!",
        welcome: "¡Bienvenido/a",
        reserved: "Hemos reservado",
        seats: "lugar(es) en tu honor",
        and: "y",
        kids_seats: "lugar(es) para niños",
        when_where: "Cuándo y Dónde",
        ceremony: "Ceremonia Religiosa",
        ceremony_date: "11 de Julio de 2026 a las 1:45 PM",
        map: "Ver iglesia en Google Maps",
        reception: "Recepción",
        cocktails: "Cócteles a partir de las",
        cocktails_time: "3:30 PM",
        map_venue: "Ver lugar en Google Maps",
        countdown: "La Cuenta Regresiva",
        days: "Días", hours: "Horas", minutes: "Minutos", seconds: "Segundos",
        dress_code: "Código de Vestimenta",
        formal: window.weddingConfig.dressCodeEs,
        women: "👗 Mujeres", men: "👔 Hombres",
        w_rule1: "Vestidos largos de noche, vestidos midi elegantes o de cóctel de gala.",
        w_rule2: "Colores recomendados: champagne, rosa viejo, dorado opaco y verde suave.",
        w_rule3: "Por favor evitar colores blancos o marfil reservados para la novia.",
        forbidden_colors_title: "Colores Prohibidos:",
        color_red: "Rojo",
        color_beige: "Beige",
        color_petroleum_blue: "Azul petróleo",
        color_navy_blue: "Azul marino",
        m_rule1: "Traje oscuro con corbata o moño, o esmoquin para un look más formal.",
        m_rule2: "Colores recomendados: negro, azul marino, carbón y verde oscuro.",
        m_rule3: "Se prefieren zapatos de vestir lustrados para ceremonia y recepción.",
        hotels: "Hoteles Sugeridos",
        view_map: "Ver en el mapa",
        photos: "Nuestras Fotos",
        registry: "Mesa de Regalos",
        gift_msg: "Su presencia es nuestro mayor regalo. Sin embargo, si desean obsequiarnos algo, estamos registrados en las siguientes tiendas.",
        thank_you: "Gracias,",
        rsvp_yes: "¡Estamos muy felices de que celebres con nosotros!",
        rsvp_adults: "Adultos reservados:",
        rsvp_kids: "Niños que asisten:",
        rsvp_no: "Gracias por avisarnos. Te extrañaremos en nuestro día especial.",
        rsvp_update: "Si necesitas actualizar tu respuesta, vuelve a utilizar tu enlace de invitation.",
        rsvp_title: "Confirmar Asistencia",
        form_name: "Nombre",
        form_attend: "¿Nos acompañarás?",
        form_yes: "¡Sí, allí estaré!",
        form_no: "Lamentablemente, no podré asistir",
        form_adults: "Número de Adultos",
        form_max_adults: "Máximo permitido para esta invitación:",
        form_kids: "Número de Niños",
        form_max_kids: "Niños permitidos en esta invitación:",
        form_diet: "Restricciones Alimenticias",
        form_submit: "Enviar RSVP",
        music_play: "Reproducir Música",
        music_pause: "Pausar Música",
        view_more: "Ver Más",
        view_less: "Ver Menos",
        bank_details_btn: "Transferencia Bancaria",
        bank_transfer_title: "Datos de Transferencia",
        bank_transfer_msg: "Puedes realizar una transferencia electrónica con los siguientes datos:",
        copy_clabe: "Copiar CLABE",
        clabe_copied: "¡CLABE Copiada! ✓"
    }
};

let currentLang = 'en';

function setLang(lang, buttonElement) {
    currentLang = lang;
    if (buttonElement) {
        document.querySelectorAll('.lang-btn').forEach(btn => btn.classList.remove('active'));
        buttonElement.classList.add('active');
    }

    // Add language class to body for easy CSS toggling
    if (lang === 'es') {
        document.body.classList.add('lang-es');
        document.body.classList.remove('lang-en');
    } else {
        document.body.classList.add('lang-en');
        document.body.classList.remove('lang-es');
    }

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            if(el.tagName === 'OPTION') {
                el.textContent = translations[lang][key];
            } else {
                el.innerHTML = translations[lang][key];
            }
        }
    });

    const dietaryEl = document.getElementById('dietary_restrictions');
    if (dietaryEl) {
        if (lang === 'es') {
            dietaryEl.placeholder = "Ej. Vegetariano, alergia a los cacahuates";
        } else {
            dietaryEl.placeholder = "E.g., Vegetarian, allergy to peanuts";
        }
    }

    updateMusicButtonText();
}

document.addEventListener('DOMContentLoaded', function() {
    setLang('es', document.querySelector('.lang-btn[onclick*="es"]'));

    // --- Bank Transfer Modal Controls ---
    const bankBtn = document.getElementById('bank-registry-btn');
    const bankModal = document.getElementById('bank-modal');
    const closeBankModal = document.getElementById('close-bank-modal');
    const btnCopyClabe = document.getElementById('btn-copy-clabe');
    const clabeNumber = document.getElementById('clabe-number');
    const copyText = document.getElementById('copy-text');

    if (bankBtn && bankModal) {
        bankBtn.addEventListener('click', function(e) {
            e.preventDefault();
            bankModal.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    }

    const closeModalFunc = function() {
        if (bankModal) {
            bankModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    if (closeBankModal) {
        closeBankModal.addEventListener('click', closeModalFunc);
    }

    if (bankModal) {
        bankModal.addEventListener('click', function(e) {
            if (e.target === bankModal) {
                closeModalFunc();
            }
        });
    }

    if (btnCopyClabe && clabeNumber) {
        btnCopyClabe.addEventListener('click', function() {
            const clabe = clabeNumber.textContent.trim();
            navigator.clipboard.writeText(clabe).then(function() {
                copyText.setAttribute('data-i18n', 'clabe_copied');
                copyText.textContent = translations[currentLang]['clabe_copied'];
                
                setTimeout(function() {
                    copyText.setAttribute('data-i18n', 'copy_clabe');
                    copyText.textContent = translations[currentLang]['copy_clabe'];
                }, 2000);
            }).catch(function(err) {
                console.error('Could not copy text: ', err);
            });
        });
    }

    const audio = document.getElementById('bg-music');
    const musicContainer = document.getElementById('music-container');

    const playPromise = audio.play();
    if (playPromise !== undefined) {
        playPromise.then(_ => {
            updateMusicButtonText();
        }).catch(error => {
            console.log("Autoplay was prevented.", error);

            const initialPlay = () => {
                audio.play().then(() => {
                    updateMusicButtonText();
                    document.body.removeEventListener('click', initialPlay);
                    document.body.removeEventListener('touchstart', initialPlay);
                }).catch(err => {
                    console.log("Manual play failed:", err);
                });
            };

            document.body.addEventListener('click', initialPlay);
            document.body.addEventListener('touchstart', initialPlay);
        });
    }

    musicContainer.addEventListener('click', toggleMusic);
});

const audio = document.getElementById('bg-music');
const musicIcon = document.getElementById('music-icon');
const musicText = document.getElementById('music-text');
const musicContainer = document.getElementById('music-container');

audio.volume = 0.4;

function updateMusicButtonText() {
    if (!audio.paused) {
        musicText.innerText = translations[currentLang]['music_pause'];
        musicIcon.innerText = "🔊";
        musicContainer.classList.add('playing');
    } else {
        musicText.innerText = translations[currentLang]['music_play'];
        musicIcon.innerText = "🔇";
        musicContainer.classList.remove('playing');
    }
}

function toggleMusic() {
    if (audio.paused) {
        audio.play().then(updateMusicButtonText).catch(error => console.log("Audio playback failed: ", error));
    } else {
        audio.pause();
        updateMusicButtonText();
    }
}

const weddingDate = new Date("July 11, 2026 14:00:00").getTime();

const timer = setInterval(function () {
    const now = new Date().getTime();
    const distance = weddingDate - now;

    if (distance < 0) {
        clearInterval(timer);
        document.getElementById("countdown").innerHTML = "<h3>Happily Married!</h3>";
        return;
    }

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    document.getElementById("days").innerText = days.toString().padStart(2, '0');
    document.getElementById("hours").innerText = hours.toString().padStart(2, '0');
    document.getElementById("minutes").innerText = minutes.toString().padStart(2, '0');
    document.getElementById("seconds").innerText = seconds.toString().padStart(2, '0');
}, 1000);

let clickCount = 0;
document.getElementById('admin-trigger').addEventListener('click', function() {
    clickCount++;
    if (clickCount === 4) {
        window.location.href = window.weddingConfig.adminLoginUrl || "/admin";
    }
    setTimeout(() => { clickCount = 0; }, 2000);
});
