import streamlit as st
import base64

st.set_page_config(
    page_title="Your App Title",  # opcjonalnie, tytuł strony
    layout="centered"                 # ustawienie szerokiego układu
)

# st.title("Hi, I'm Michał Ostaszewski 👋")

# # Wyświetlamy zdjęcie (placeholder, zamień URL na swoje zdjęcie, jeśli chcesz)
# st.image("/Users/michal/PycharmProjects/Stock Scraper/Images/DSC08336.jpg", width=270)
#
# # Funkcja do konwertowania lokalnego obrazu na URL
# def get_base64_image(path):
#     with open(path, "rb") as file:
#         return base64.b64encode(file.read()).decode()
#
# image_base64 = get_base64_image("/Users/michal/PycharmProjects/Stock Scraper/Images/LinkedIn_logo_initials.png")
#
#
# # Ikonki do profili
# st.markdown(f"""
#     <div class="profile-links">
#         <a href="https://www.linkedin.com/in/michael-ostaszewski/" target="_blank">
#             <img src="data:image/png;base64,{image_base64}" alt="LinkedIn" width="50">
#         </a>
#     </div>
# """, unsafe_allow_html=True)

# Funkcja do konwertowania lokalnego obrazu na URL
def get_base64_image(path):
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode()

# Ścieżki do obrazów
profile_picture_path = "/Users/michal/PycharmProjects/Stock Scraper/Images/DSC08336.jpg"
linkedin_logo_path = "/Users/michal/PycharmProjects/Stock Scraper/Images/LinkedIn_logo_initials.png"
github_logo_path = "/Users/michal/PycharmProjects/Stock Scraper/Images/Octicons-mark-github.svg.png"
email_logo_path = "/Users/michal/PycharmProjects/Stock Scraper/Images/Gmail_icon_(2020).svg.png"

# Konwersja obrazów na Base64
linkedin_logo_base64 = get_base64_image(linkedin_logo_path)
github_logo_base64 = get_base64_image(github_logo_path)
email_logo_base64 = get_base64_image(email_logo_path)

# Tworzymy kolumny
col1, col2 = st.columns(2)

# Pierwsza kolumna: Zdjęcie profilowe
with col1:
    st.image(profile_picture_path, width=270)

# Druga kolumna: Ikony do profili
with col2:
    st.markdown("""
        <h2>Michał Ostaszewski</h2>
        <h5>Find me on: </h5>
    """, unsafe_allow_html=True)
    st.markdown(f"""
        <style>
            .profile-links a img {{
                margin-right: 25px; /* Odstęp między ikonami */
            }}
            .profile-links a:last-child img {{
                margin-right: 0; /* Usuń odstęp dla ostatniej ikony */
            }}
        </style>

        <!-- Sekcja z ikonami LinkedIn i GitHub -->
        <div class="profile-links" style="display: flex; align-items: center; margin-bottom: 20px;">
            <a href="https://www.linkedin.com/in/michael-ostaszewski/" target="_blank">
                <img src="data:image/png;base64,{linkedin_logo_base64}" alt="LinkedIn" width="40">
            </a>
            <a href="https://github.com/michael-ostaszewski" target="_blank">
                <img src="data:image/png;base64,{github_logo_base64}" alt="GitHub" width="40">
            </a>
        </div>

        <!-- Sekcja Contact me -->
        <h5>Contact me:</h5>
        <div class="profile-links" style="display: flex; align-items: center;">
            <a href="mailto:mostaszewski.photo@gmail.com" target="_blank">
                <img src="data:image/png;base64,{email_logo_base64}" alt="Email" width="40">
            </a>
        </div>
    """, unsafe_allow_html=True)

st.markdown("""

    Data Science naturally became a part of my life. From a young age, I was fascinated by the exact sciences, particularly physics and astronomy. However, due to my involvement in sports (I trained in speed skating for 12 years, reaching the national team level), I didn't pursue studies in these fields. 
    
    Nevertheless, my passion for science remained strong, leading me to deeply explore astrophotography. This passion resulted in a large-scale project: creating a multi-gigapixel image of the Milky Way—an endeavor that required merging thousands of individual photographs into one massive image. While this project might be classified as photography, in reality, it was much closer to physics, data analysis, and computer science due to the complexity of the process and the volume of data involved. The final result and the full story behind this project can be found here: [Milky Way Project](https://www.astrobin.com/u3ny4o/0/).

    As I explored more analytical tools and techniques, I began to recognize the immense potential of integrating data with modern technologies. The breakthrough moment for me came with the emergence of tools like ChatGPT and generative AI, which opened up new perspectives and possibilities. This reinforced my conviction that leveraging AI and Data Science is the path I want to pursue, as I see an ocean of opportunities in these fields.

    To deepen my expertise, I decided to further my education. I completed a postgraduate degree in **Big Data Engineering** at the **Polish-Japanese Academy of Information Technology in Warsaw**, which provided me with a strong theoretical foundation and practical skills in analyzing large datasets. Thanks to this, I can now implement ambitious projects in my daily life using Data Science, such as this project analyzing **S&P 500 stocks** or the story of how I used Data Science to win a **12-hour cycling marathon**: [Read the story](https://www.linkedin.com/feed/update/urn:li:activity:7248368704088948738/).

    Alongside developing my Data Science skills, I currently work as a **Performance Marketing Specialist** at one of the largest marketing agencies in Poland, collaborating daily with top brands in the industry. In this role, beyond using ads managing systems I use everyday tools like **Excel, Looker, and Python (mainly the Pandas library)** for data analysis and optimizing advertising campaigns. Additionally, this position has given me valuable experience in client communication, which I find extremely important—today, combining **technical expertise with strong communication skills** is crucial.

    I am a person who constantly strives for growth and expanding my competencies. Every new project is an opportunity to learn and refine my skills. However, I aspire to be closer to the technologies shaping the world around us, which is why I am now applying for a **Data Scientist** position. I believe that with my **experience and education**, I can bring significant value to your company.

    Thanks for taking the time to read this. Feel free to **connect with me on [LinkedIn](https://www.linkedin.com/in/michael-ostaszewski/)** or check out my **[projects on GitHub](https://github.com/michael-ostaszewski/)**.
""", unsafe_allow_html=True)

st.image("/Users/michal/PycharmProjects/Stock Scraper/Images/_DSC3581.jpg", caption="Collecting photons from millions of stars in our galaxy for my Milky Way Project, Namibia 2021.", width=700)


st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("""
    <p style="font-size: 12px; text-align: left; color: gray;">
        Website made by @Michał Ostaszewski
    </p>
""", unsafe_allow_html=True)

# import streamlit as st
# from PIL import Image
# import base64
#
# # Wczytaj swoje zdjęcie profilowe
# profile_pic = "/Users/michal/PycharmProjects/Stock Scraper/Images/DSC08336.jpg"  # Zamień na ścieżkę do swojego zdjęcia
# image = Image.open(profile_pic)
#
# # Ustawienia strony
# st.set_page_config(page_title="Moje Portfolio", page_icon="🌟")
#
# # Styl CSS
# st.markdown("""
#     <style>
#         .profile-section {
#             text-align: center;
#         }
#         .profile-picture {
#             border-radius: 50%;
#             margin-bottom: 15px;
#             width: 150px;
#             height: 150px;
#         }
#         .profile-links a {
#             margin: 0 10px;
#             text-decoration: none;
#             font-size: 25px;
#         }
#         .profile-links a:hover {
#             opacity: 0.7;
#         }
#     </style>
# """, unsafe_allow_html=True)
#
# # Sekcja profilu
# st.markdown('<div class="profile-section">', unsafe_allow_html=True)
#
# # Wyświetl zdjęcie profilowe
# st.image(image, caption=None, width=150, use_container_width=False)
#
# # Nazwa i opis
# st.markdown("""
#     <h1>Twoje Imię</h1>
#     <p>Lubię analizować dane i budować modele predykcyjne 🧠🤖✨</p>
# """, unsafe_allow_html=True)
#
# # Funkcja do konwertowania lokalnego obrazu na URL
# def get_base64_image(path):
#     with open(path, "rb") as file:
#         return base64.b64encode(file.read()).decode()
#
# image_base64 = get_base64_image("/Users/michal/PycharmProjects/Stock Scraper/Images/LinkedIn_logo_initials.png")
#
#
# # Ikonki do profili
# st.markdown(f"""
#     <div class="profile-links">
#         <a href="https://www.linkedin.com/in/your_profile" target="_blank">
#             <img src="data:image/png;base64,{image_base64}" alt="LinkedIn" width="30">
#         </a>
#     </div>
# """, unsafe_allow_html=True)
#
# st.markdown('</div>', unsafe_allow_html=True)

# Data Science came naturally into my life. As a child, I was fascinated by physics and astronomy, and I later pursued a project in astrophotography where I created a gigapixel image of the Milky Way. This early passion for the sciences naturally led me to Data Science and programming.
#
# With the emergence of tools like ChatGPT and generative AI, I became even more captivated by the potential of these technologies. I furthered my education by completing postgraduate studies in Big Data Engineering at a Polish technical school. Today, I continue to develop my Data Science skills through projects like this one and by actively investing in the stock market.
#
# Connect with me on [LinkedIn](https://www.linkedin.com/in/michael-ostaszewski/) or check out my projects on [GitHub](http://github.com/michael-ostaszewski).
#
# *Disclaimer: Investing involves risk, and the opinions expressed on this site are my own. This site does not constitute financial advice.*
# """)