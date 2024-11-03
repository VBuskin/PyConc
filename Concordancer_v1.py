import streamlit as st
import spacy
import pandas as pd
import re
from io import BytesIO
from pathlib import Path
import json
import gzip

# Load spaCy's English model
nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])

def load_compressed_index(file):
    """Load the compressed JSON index file."""
    try:
        with gzip.open(file, 'rt', encoding='utf-8') as f:
            data = json.load(f)
            return {
                'texts': data['texts'],
                'token_positions': {k: [(f, p) for f, p in v] 
                                 for k, v in data['token_positions'].items()}
            }
    except Exception as e:
        raise ValueError(f"Error loading index file: {str(e)}")

# Title of the app
st.title("PyConc Concordancer")

# Create file uploader for the index file
uploaded_file = st.file_uploader("Upload corpus index file (.json.gz)", type=["gz"])

if uploaded_file:
    try:
        # Load the index
        corpus_data = load_compressed_index(uploaded_file)
        st.write(f"Successfully loaded index with {len(corpus_data['texts'])} files")
        
        # Search options
        st.subheader("Search Options")
        search_term = st.text_input(
            "Enter regex search term:",
            help="Use patterns like: \\w+ing (words ending in 'ing'), \\b\\w{4}\\b (4-letter words), etc."
        )
        
        case_sensitive = st.checkbox("Case sensitive search", value=False)
        context_window = st.slider("Context window size (words)", min_value=1, max_value=10, value=5)
        
        if search_term:
            all_concordance_data = []
            
            try:
                # Compile regex pattern
                pattern = re.compile(search_term, flags=0 if case_sensitive else re.IGNORECASE)
                
                # Search through all texts
                for filename, text in corpus_data['texts'].items():
                    for match in pattern.finditer(text):
                        start, end = match.span()
                        matched_text = match.group()
                        
                        # Get context by splitting the text around the match
                        pre_text = text[:start].split()
                        post_text = text[end:].split()
                        
                        pre_context = " ".join(pre_text[-context_window:] if len(pre_text) > context_window else pre_text)
                        post_context = " ".join(post_text[:context_window] if len(post_text) > context_window else post_text)
                        
                        all_concordance_data.append((filename, pre_context, matched_text, post_context))
                
                # Display results
                if all_concordance_data:
                    total_occurrences = len(all_concordance_data)
                    st.write(f"Found {total_occurrences} occurrences across {len(corpus_data['texts'])} files.")
                    
                    # Create DataFrame with results
                    concordance_df = pd.DataFrame(
                        all_concordance_data,
                        columns=['File', 'Pre-Context', 'Match', 'Post-Context']
                    )
                    
                    # Add filtering options
                    st.subheader("Filter Results")
                    with st.expander("Select files to include in results"):
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
    
    except Exception as e:
        st.error(f"Error processing index file: {str(e)}")
        st.info("Please make sure you're uploading a valid corpus index file.")
