Chinese Learning App

Project Overview:

The goal of the app is to help primary school students learn Chinese, esepecially simplied Chinese characters. Each user should have their own profile to track their learnings, progresses, mistakes, and more. The system provides multiple modules of functions.

Skills Required
* Backend server development
* Backend database management
* Frontend user interface development
* System logging

Chinese character data

I have data on 3000 common simplifed chinese character cards.
* There are 3000 folders in the  `/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯氏早教识字卡/png` folder. All folders are named using a `<dddd>` pattern. The names correspond to the character cards' index numbers.
* Each `<dddd>` folder has 2 PNG files. `page1.png` is the front of the character card. `page2.png` is the back of the character card.
* The front side of a character card is a full size simplified Chinese character. The back side of the character card contains more detailed information of the simplified Chinese character.
    * The character
    * The pinyin
    * The radical
    * The number of strokes
    * A sample sentence (例句)
    * A few sample words (词组)
    * The order of strokes (笔顺)
    * The structure (结构), e.g. 左右结构，上下结构，半包围结构，etc
* The structured information of all character cards is stored in the `/Users/jarodm/github/jarodmeng/daydreamedu-scripts/chinese_chr_app/extract_characters_using_ai/output` folder.
    * The `characters.csv` file contains the information in a CSV format. Each row is a character card, so there should be 3000 rows in the file (excluding the header row).
    * The `characters.json` file contains the information in a JSON format.
    * The fields of information included in the CSV and JSON files are the following:
        * **custom_id** (string): The character card index number in `<dddd>` format (e.g., "0001", "0002", "3000")
        * **Index** (string): The character card index number, same as custom_id
        * **Character** (string): The simplified Chinese character itself (e.g., "爸", "妈")
        * **Pinyin** (array/string): The pinyin pronunciation(s) of the character. 
            * In CSV format: Stored as a JSON string array (e.g., `["bà"]` or `["mā", "má", "mǎ", "mà"]` for characters with multiple pronunciations)
            * In JSON format: Parsed as an actual array of strings (e.g., `["bà"]` or `["mā", "má", "mǎ", "mà"]`)
            * Tone marks are required (e.g., "bà" not "ba")
        * **Radical** (string): The radical component of the character (e.g., "父", "女")
        * **Strokes** (string): The number of strokes required to write the character (e.g., "8", "6")
        * **Structure** (string): The structural classification of the character (e.g., "左右结构", "上下结构", "半包围结构")
        * **Sentence** (string): A sample sentence (例句) that uses the character in context. This field is optional and may be empty for some characters.
        * **Words** (array/string): Sample words/phrases (词组) that contain the character.
            * In CSV format: Stored as a JSON string array (e.g., `["爸爸", "爸妈"]`)
            * In JSON format: Parsed as an actual array of strings (e.g., `["爸爸", "爸妈"]`)
            * This field is optional and may be an empty array `[]` for some characters.

Key Features

Milestone 1: A search function to learn about a particular character
* A website for now. We will build it into a mobile app in future milestones.
* No user profile yet. We will build per-user profiles in future milestones.
* When the website loads, it has a search box in the middle of the page.
* The user can input a simplified Chinese character to search.
    * If the character is found in the 3000 character cards, display page 1 and page 2 of the character card side by side below the search bar.
    * If the character is not found, display an error message and ask the user to input a new character.