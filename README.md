# MusicReader
MusicReader is an app that lets you turn your music box paper scoresheet scans into MIDI music, complete with tempo adjustment, transposition and addition of silences at the start and the end of your music tracks!

![MusicReader Preview]([https://github.com/LPBeaulieu/Typewriter-OCR-TintypeText/blob/main/TintypeText%20basic%20rtf%20mode%20screenshot.jpg](https://github.com/LPBeaulieu/MusicReader/blob/main/MusicReader.png))
<h3 align="center">MusicReader</h3>
<div align="center">
  
  [![License: AGPL-3.0](https://img.shields.io/badge/License-AGPLv3.0-brightgreen.svg)](https://github.com/LPBeaulieu/MusicReader/blob/main/LICENSE)
  ![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
  ![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
  
</div>

---

<p align="left"> <b>MusicReader</b> is an application that generates MIDI files from scanned music box scoresheet JPEG files, complete with features such as tempo adjustment, transposition, and addition of silence to the start and end of the MIDI files, essentially turning your music box into an analog version of a Digital Audio Workstation (DAW)!
</p>

## 📝 Table of Contents
- [Getting Started](#getting_started)
- [Usage](#usage)
- [Author](#author)
- [Acknowledgments](#acknowledgments)

## 🏁 Getting Started <a name = "getting_started"></a>

The following instructions will be provided in great detail, as they are intended for a broad audience and will
allow to run a copy of <b>MusicReader</b> on a local computer. 

<b>Step 1</b>- Create a virtual environment (called <i>env</i>, or any other name of your choosing) in your working folder:
```
python3 -m venv env
```

<b>Step 2</b>- Activate the <i>env</i> virtual environment <b>(you will need to do this step every time you use the Python code files)</b> 
in your working folder:

For Windows
```
env/Scripts/activate 
```
For Linux:
```
source env/bin/activate
```

<b>Step 3</b>- Install <b>NumPy</b> (Python library for data array transformations)
```
pip install numpy
```

<b>Step 4</b>- Install <b>OpenCV</b> (Python library for image manipulation and annotation):
```
pip install opencv-python
```

<b>Step 5</b>- Install <b>Mido</b> (Python module for MIDI file generation):
```
pip install mido
```

<b>Step 6</b>- You're now ready to use <b>MusicReader</b>! 🎉

## 🎈 Usage <a name="usage"></a>
Here are a few important pointers for best results:

- You will need to **line the lid of your flatbed scanner with black construction paper** (you may use masking tape to stick the paper, as it should not damage your lid). The application detects the punched holes as black circles when **the underside of the scoresheets are scanned**, meaning that the grid faces up. The underside of the scoresheet are scanned in order to remove any superfluous grid information that might hinder the punched hole detection. The black areas above, below and on either side of the scoresheet will also let the code auto-crop the scoresheet.

- The scoresheets need to be sized to a maximum of around 11 inches in length in order to fit on a standard flatbed scanner **configured to scan in US Legal format (8.5 x 14 inches)** to avoid having information being cut off from your scans. Try to **cut the strips nice and straight at right angles** with the length of the scoresheet, as the code will detect any horizontal spaces left after the last note of a given scoresheet and add it to the horizontal space before the first note on the next image. This way, the timing of your notes should still be fairly accurate even when notes span several scoresheet strips. 

- Make sure to **scan at a resolution of 200 dots per inch (dpi) or higher** for more accurate results (I had great results with 200 dpi, which keeps the file sizes manageable) and output the files as **grayscale or color JPEG images** (grayscale will take up less storage space). You should also select the **lightest scanning setting** on your scanner, as this helps to bleach out any blemishes or shadows that might be present on the scanned underside of your scoresheets. 

- The **scanned JPEG file names should end with a plus sign (“+”)**, such that when your scanner automatically suffixes the JPEG files with a file number, the code will be able to distinguish these from any numbers present at the end of your actual file names (e.g., “Track 1+0001.jpg).

- When placing the scoresheet grid-side up onto your flatbed scanner, **line up the scoresheet strip such that it shows up on the left side of the scan in portrait mode** (the “Page Rotation Angle” setting in the “Image Processing Settings Menu” should then be -90 degrees, which is 90 degrees counterclockwise), and **always have the arrow pointing in the same direction**. See the example JPEG image (“this is what your scans should look like.jpg”) in the working folder to illustrate this. In my case, on an all-in-one printer, I had to place the scoresheet at the very bottom of the flatbed area (grid-side up), with the arrow pointing to the right. This way, it was easier to line up the strip with the lower edge of the scanning area before closing the lid. **Make sure to horizontally center the scoresheet** (the long edge of the scoresheet should be centered with the long edge of the flatbed scanner’s scanning area) to avoid having the edges of the strip being cut off, as this could affect the timing of the song.

- **Place your JPEG scans within the "Scans" subfolder** of the working folder (the folder where the **MusicReader** executable is located is the working folder).

- The default settings should work well in most cases, and every setting is explained in detail in the command-line interface menus of **MusicReader**, with the default values being specified in every case.

        
  <br><b>And that's it!</b> Happy (analog) composing with your new AAW (Analog Audio Workstation)! 🎉📖
  
  
## ✍️ Authors <a name = "author"></a>
- 👋 Hi, I’m Louis-Philippe!
- 👀 I’m interested in natural language processing (NLP) and anything to do with words, really! 📝
- 🌱 I’m currently reading about deep learning (and reviewing the underlying math involved in coding such applications 🧮😕)
- 📫 How to reach me: By e-mail! LPBeaulieu@gmail.com 💻


## 🎉 Acknowledgments <a name = "acknowledgments"></a>
- Hat tip to [@kylelobo](https://github.com/kylelobo) for the GitHub README template!




<!---
LPBeaulieu/LPBeaulieu is a ✨ special ✨ repository because its `README.md` (this file) appears on your GitHub profile.
You can click the Preview link to take a look at your changes.
--->
