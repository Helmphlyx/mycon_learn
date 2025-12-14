This is a great project! As a Software Engineer, you'll appreciate a structured Design Doc (RFC style) that you can feed into Claude (or Cursor/Copilot) to generate the boilerplate code.

Since your goal is improving **literacy** (spelling/diacritics), the critical component here is **strict input validation**-the program shouldn't accept "ca" if the answer is "cà".

Here is the Design Document for **"VietFlash" (Local Vietnamese Practice App)**.

# 📝 **Design Doc: VietFlash (Local Practice App)**

## **1\. Overview**

**VietFlash** is a locally hosted web application designed to help a heritage Vietnamese speaker improve their reading and writing literacy. It presents flashcards in a bidirectional manner (Eng \$\\to\$ Viet / Viet \$\\to\$ Eng) and enforces strict diacritic spelling.

## **2\. Goals & Non-Goals**

- **Goal:** Provide a clean UI for practicing translation.
- **Goal:** Enforce correct tone/diacritic usage in answers.
- **Goal:** Allow the user to easily add new words (JSON/CSV or UI input).
- **Non-Goal:** Mobile app store release (this is a local host tool).
- **Non-Goal:** Complex User Auth (Single user system).

## **3\. Tech Stack**

- **Backend:** Python (FastAPI or Flask) - _Chosen for ease of local hosting and string manipulation._
- **Database:** SQLite or a simple vocab.json file - _SQLite is preferred to track "spaced repetition" statistics later._
- **Frontend:** HTML5 / JavaScript (Vanilla or Vue.js via CDN) / TailwindCSS - _Keep it lightweight, no complex build steps (npm/webpack) if possible, to make it easy to modify._

## **4\. Core Features**

### **4.1. The Quiz Loop**

- **Display Phase:** Show a word in the Source Language (e.g., English: "Tomorrow").
- **Input Phase:** User types the target translation into a text box.
  - _Constraint:_ Must support Unicode input (standard OS keyboard or built-in VI input library).
- **Validation Phase:**
  - User hits "Enter".
  - Backend normalizes strings (trim whitespace, lower case).
  - **Strict Comparison:** input == answer.
- **Result Phase:**
  - **Correct:** Green flash, play a success sound, load next card.
  - **Incorrect:** Red flash, show the "Diff" (e.g., You typed ma, Answer is má).

### **4.2. Hint System**

- **Hint Level 1:** Show the number of words/syllables (e.g., __ _ for "ba").
- **Hint Level 2:** Reveal the first letter of each word (e.g., n_\__ m__ for "ngày mai").
- **Hint Level 3:** Show the definition/context sentence.

### **4.3. Data Management**

- A "Seed" file (vocabulary.json) that the user can manually edit to add words from their daily Youtube watching.

## **5\. Data Model (Schema)**

If using SQLite, the table cards would look like this:

SQL

CREATE TABLE cards (  
id INTEGER PRIMARY KEY,  
vietnamese TEXT NOT NULL, -- e.g., "ngày mai"  
english TEXT NOT NULL, -- e.g., "tomorrow"  
category TEXT, -- e.g., "common", "food", "slang"  
difficulty_level INTEGER DEFAULT 1,  
success_count INTEGER DEFAULT 0, -- For tracking progress  
last_reviewed TIMESTAMP  
);  

## **6\. API Endpoints (REST)**

- GET /api/card/random: Returns a random card JSON.
  - _Query Param:_ ?mode=eng_to_viet or ?mode=viet_to_eng.
- POST /api/check: Accepts { card_id: 1, user_input: "..." }.
  - Returns { correct: boolean, diff: string }.
- POST /api/card: Add a new word to the deck.

## **7\. UI Mockup (Mental Model)**

+------------------------------------------------------+  
| \[Header: VietFlash Practice\] \[Stats: 10/12\] |  
+------------------------------------------------------+  
| |  
| \[ LARGE ENGLISH WORD: "Hello" \] |  
| |  
| \[ Input Field (Type Vietnamese) \] |  
| |  
| \[ Submit Button \] \[ Hint? \] |  
| |  
+------------------------------------------------------+  
| (Hidden Area: Result Message "Correct! It's Chào") |  
+------------------------------------------------------+  

## **8\. Implementation Prompts (For Claude)**

Since you are using Claude Code, you can use these specific prompts to generate the app in modular chunks.

**Prompt 1 (Backend Setup):**

"Act as a Senior Python Engineer. Create a simple FastAPI backend with SQLite for a language learning app. Create a Card model with fields: id, vietnamese, english, and success_count. Create two endpoints: one to get a random card, and one to validate a user's answer (string comparison). Use Pydantic models."

**Prompt 2 (Frontend Setup):**

"Create a single index.html file using TailwindCSS via CDN and Vue.js (or Vanilla JS). It should fetch a random card from the /api/card/random endpoint. Display the word in the center. Create an input field for the answer. When the user presses Enter, send the answer to /api/check and display a Green or Red banner based on the result."

**Prompt 3 (Data Seeding):**

"Write a python script to seed the SQLite database with these 10 common Vietnamese words: \[Insert the list of words we discussed earlier\]."

## **9\. Special Considerations for Vietnamese**

Since you mentioned you "never learned to write," you might struggle with **typing** the accents on your keyboard.

- **Option A (OS Level):** You install the Vietnamese keyboard on Windows/Mac (Telex is best). This is the best long-term skill.
- **Option B (App Level):** You ask Claude to include a library like avim.js in the frontend code. This allows you to type nguoiwf and it automatically converts to người inside the input box, even if your computer doesn't have the keyboard installed.

**Recommendation:** Go with **Option A**. Learning the physical key combinations (Telex) is part of the literacy journey.
ate the **JSON seed file** with the words/sentences we practiced today (and the song lyrics) so you have immediate data to populate your database?
