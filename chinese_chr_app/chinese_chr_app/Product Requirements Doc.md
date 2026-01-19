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
* The structured information of all character cards is stored in the `/Users/jarodm/github/jarodmeng/daydreamedu-scripts/chinese_chr_app/data` folder.
    * The `characters.json` file contains the information in a JSON format. This is the primary data format used by the application.
    * The fields of information included in the structured data (currently stored in `characters.json`) are the following:
        * **custom_id** (string): The character card index number in `<dddd>` format (e.g., "0001", "0002", "3000")
        * **Index** (string): The character card index number, same as custom_id
        * **Character** (string): The simplified Chinese character itself (e.g., "爸", "妈")
        * **Pinyin** (array of strings): The pinyin pronunciation(s) of the character.
            * Tone marks are required (e.g., "bà" not "ba")
        * **Radical** (string): The radical component of the character (e.g., "父", "女")
        * **Strokes** (string): The number of strokes required to write the character (e.g., "8", "6")
        * **Structure** (string): The structural classification of the character (e.g., "左右结构", "上下结构", "半包围结构")
        * **Sentence** (string): A sample sentence (例句) that uses the character in context. This field is optional and may be empty for some characters.
        * **Words** (array of strings): Sample words/phrases (词组) that contain the character. This field is optional and may be an empty array `[]` for some characters.

Key Features

Milestone 1: A search function to learn about a particular character
* A website for now. We will build it into a mobile app in future milestones.
* No user profile yet. We will build per-user profiles in future milestones.
* When the website loads, it has a search box in the middle of the page.
* The user can input a simplified Chinese character to search.
    * If the character is found in the 3000 character cards, display page 1 and page 2 of the character card side by side below the search bar.
        * Display the other meta data (extracted from the 冯氏早教识字卡 back-side information) in a table below the card png files: 拼音，部首，笔画，例句，词组，结构.
            * If the information is dictionary-corrected (i.e., adjusted from the original 冯氏早教识字卡 data based on dictionary sources), strip the " (dictionary)" part from the information in display, but make the color red.
            * Make the table cells editable. The user can double click the cell to edit it and press enter to complete the edit. If the edited value is different from the stored data, prompt a dialog to ask the user if they indeed want the information changed. If they click yes, edit the stored data. We should also log every change in a logging file.
        * Also display meta data (extracted from hwxnet) in a table: 拼音，部首，总笔画，基本解释，英语
    * If the character is not found, display an error message and ask the user to input a new character.

Milestone 2: A radicals page to organize characters by radical
* A new page named "部首 (Radicals)" accessible from the main search page via navigation links.
* The radicals page displays all unique radicals in a grid layout with clickable boxes.
* Each radical box shows:
    * The radical character displayed in KaiTi (楷体) font
    * The number of characters associated with that radical
* Radicals are sorted by the number of associated characters (descending order), with radicals having more characters appearing first.
* When a user clicks on a radical box, they are directed to a detail page dedicated to that radical.
* The radical detail page shows:
    * All characters associated with the selected radical
    * Each character is displayed in a clickable box showing:
        * The character in KaiTi (楷体) font
        * The pinyin pronunciation(s)
        * The number of strokes
    * Characters are sorted first by number of strokes (ascending), then by pinyin (alphabetically)
    * Clicking on a character box navigates to the search page with that character pre-filled
* Navigation links are available on all pages to switch between the search page, radicals page, and (after Milestone 3) the structures page.
* The radicals data is generated dynamically from `characters.json` on-the-fly and cached in memory for efficient performance, ensuring it stays synchronized with any character edits.

Milestone 3: A structures page to organize characters by structure
* A new page named "结构 (Structures)" accessible from the main search page via navigation links.
* The structures page displays all unique structure types in a grid layout with clickable boxes.
* Each structure box shows:
    * The structure type name (e.g., "左右结构", "上下结构", "半包围结构")
    * The number of characters associated with that structure type
* Structure types are sorted by the number of associated characters (descending order), with structure types having more characters appearing first.
* When a user clicks on a structure box, they are directed to a detail page dedicated to that structure type.
* The structure detail page shows:
    * All characters associated with the selected structure type
    * Each character is displayed in a clickable box showing:
        * The character in KaiTi (楷体) font
        * The pinyin pronunciation(s)
        * The number of strokes
    * Characters are sorted first by number of strokes (ascending), then by pinyin (alphabetically)
    * Clicking on a character box navigates to the search page with that character pre-filled
* Navigation links are available on all pages to switch between the search page, radicals page, and structures page.
* The structures data is generated dynamically from `characters.json` on-the-fly and cached in memory for efficient performance, ensuring it stays synchronized with any character edits.