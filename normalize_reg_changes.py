def normalize_registration_number(reg_number):
    """Normalize registration number by removing spaces, hyphens and converting to uppercase"""
    if not reg_number:
        return reg_number
    
    # Remove spaces, hyphens and other special characters
    reg_number = re.sub(r'[^a-zA-Z0-9]', '', reg_number)
    
    # Convert to uppercase
    return reg_number.upper()
