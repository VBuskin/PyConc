import streamlit as st
import spacy
import pandas as pd
import re
from io import BytesIO
from pathlib import Path
import tempfile
import os
import chardet

# Load spaCy's English model
nlp = spacy.load("en_core_web_sm")

def detect_and_read_file(file):
    """
    Detect the encoding of a file and read its contents.
    Returns tuple of (text, encoding_used)
    """
    # Read the binary content
    raw_data = file.read()
    file.seek(0)  # Reset file pointer
    
    # Detect encoding
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    
    # List of encodings to try if detection fails
    fallback_encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'ascii']
    
    # Try detected encoding first
    if encoding:
        try:
            text = raw_data.decode(encoding)
            return text, encoding
        except UnicodeDecodeError:
            pass
    
    # Try fallback encodings
    for enc in fallback_encodings:
        try:
            text = raw_data.decode(enc)
            return text, enc
        except UnicodeDecodeError:
            continue
    
    raise UnicodeDecodeError(f"Failed to decode file with any of the attempted encodings: {', '.join(fallback_encodings)}")

# Title of the app
st.title("Multi-file Concordance Search App")

# Create file uploader for multiple files
uploaded_files = st.file_uploader("Choose text files", type="txt", accept_multiple_files=True)

if uploaded_files:
    # Display number of uploaded files
    st.write(f"Number of files uploaded: {len(uploaded_files)}")
    
    # Create a progress bar for file processing
    progress_bar = st.progress(0)
    
    # Initialize combined text and file tracking
    all_concordance_data = []
    file_encodings = {}  # Track encodings used for each file
    
    # Search options
    st.subheader("Search Options")
    search_type = st.radio(
        "Select search type:",
        ["Simple Keyword", "Regular Expression"],
        help="Simple keyword search matches exact words. Regular expression allows for pattern matching."
    )
    
    search_term = st.text_input(
        "Enter search term:",
        help="For regex, you can use patterns like: \w+ing (words ending in 'ing'), \b\w{4}\b (4-letter words), etc."
    )
    
    case_sensitive = st.checkbox("Case sensitive search", value=False)
    context_window = st.slider("Context window size (words)", min_value=1, max_value=10, value=5)
    
    if search_term:
        try:
            # Compile regex if using regex search
            if search_type == "Regular Expression":
                if case_sensitive:
                    pattern = re.compile(search_term)
                else:
                    pattern = re.compile(search_term, re.IGNORECASE)
            
            # Process each file
            for idx, uploaded_file in enumerate(uploaded_files):
                # Update progress bar
                progress = (idx + 1) / len(uploaded_files)
                progress_bar.progress(progress)
                
                try:
                    # Read and detect encoding
                    text, encoding = detect_and_read_file(uploaded_file)
                    filename = uploaded_file.name
                    file_encodings[filename] = encoding
                    
                    if search_type == "Simple Keyword":
                        # Use spaCy for keyword search
                        doc = nlp(text)
                        for i, token in enumerate(doc):
                            token_text = token.text if case_sensitive else token.text.lower()
                            search_text = search_term if case_sensitive else search_term.lower()
                            
                            if token_text == search_text:
                                pre_context = " ".join([t.text for t in doc[max(0, i - context_window):i]])
                                post_context = " ".join([t.text for t in doc[i + 1:i + 1 + context_window]])
                                all_concordance_data.append((filename, pre_context, token.text, post_context))
                    
                    else:  # Regex search
                        # Find all regex matches
                        for match in pattern.finditer(text):
                            start, end = match.span()
                            matched_text = match.group()
                            
                            # Get context by splitting the text around the match
                            pre_text = text[:start].split()
                            post_text = text[end:].split()
                            
                            # Extract context windows
                            pre_context = " ".join(pre_text[-context_window:] if len(pre_text) > context_window else pre_text)
                            post_context = " ".join(post_text[:context_window] if len(post_text) > context_window else post_text)
                            
                            all_concordance_data.append((filename, pre_context, matched_text, post_context))
                
                except Exception as e:
                    st.error(f"Error processing file {uploaded_file.name}: {str(e)}")
                    continue
            
            # Display encoding information
            st.subheader("File Encoding Information")
            encoding_df = pd.DataFrame(
                [(file, enc) for file, enc in file_encodings.items()],
                columns=['File', 'Encoding Used']
            )
            st.dataframe(encoding_df)
            
            # Display results as a table
            if all_concordance_data:
                total_occurrences = len(all_concordance_data)
                st.write(f"Found {total_occurrences} occurrences across {len(uploaded_files)} files:")
                
                # Create DataFrame with file information
                concordance_df = pd.DataFrame(
                    all_concordance_data,
                    columns=['File', 'Pre-Context', 'Match', 'Post-Context']
                )
                
                # Add filtering options
                st.subheader("Filter Results")
                selected_files = st.multiselect(
                    "Filter by files:",
                    options=sorted(concordance_df['File'].unique()),
                    default=sorted(concordance_df['File'].unique())
                )
                
                # Apply filters
                filtered_df = concordance_df[concordance_df['File'].isin(selected_files)]
                
                # Display filtered results
                st.dataframe(filtered_df)
                
                # Summary statistics
                st.subheader("Summary Statistics")
                file_stats = concordance_df['File'].value_counts().reset_index()
                file_stats.columns = ['File', 'Occurrences']
                st.write("Occurrences per file:")
                st.dataframe(file_stats)
                
                if search_type == "Regular Expression":
                    pattern_stats = concordance_df['Match'].value_counts().reset_index()
                    pattern_stats.columns = ['Matched Pattern', 'Count']
                    st.write("Match pattern distribution:")
                    st.dataframe(pattern_stats)
                
                # Export options
                st.subheader("Export Results")
                
                csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv_data,
                    file_name="concordance_results.csv",
                    mime="text/csv"
                )
                
                xlsx_data = BytesIO()
                filtered_df.to_excel(xlsx_data, index=False, engine='xlsxwriter')
                xlsx_data.seek(0)
                st.download_button(
                    label="Download as Excel",
                    data=xlsx_data,
                    file_name="concordance_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.write(f"No matches found for '{search_term}' in any of the files.")
        
        except re.error as e:
            st.error(f"Invalid regular expression: {str(e)}")
            st.info("Please check your regex pattern syntax.")
    
    # Reset progress bar
    progress_bar.empty()