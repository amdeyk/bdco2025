import os

# Define the path to the file to be patched
file_to_patch = "admin.py"

# --- Code blocks for replacement ---

# This is the original code block related to drawing guest info on the badge.
original_code_block = """    # Guest Name
    name_y = info_y
    name_height = 100
    if len(guest_name) > 20:
        words = guest_name.split(' ')
        if len(words) > 1:
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])
            try:
                draw.text((info_x + info_width//2, name_y + 35), line1, fill=navy_blue, anchor="mm", font_size=35)
                draw.text((info_x + info_width//2, name_y + 75), line2, fill=navy_blue, anchor="mm", font_size=35)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + 35), line1, fill=navy_blue, anchor="mm")
                draw.text((info_x + info_width//2, name_y + 75), line2, fill=navy_blue, anchor="mm")
        else:
            try:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=35)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")
    else:
        try:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=40)
        except TypeError:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")

    # Guest Role
    role_y = name_y + name_height + 20
    role_height = 60
    try:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='white', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='white', anchor="mm")

    # Guest ID
    id_y = role_y + role_height + 20
    id_height = 60
    guest_id = guest.get('ID', 'UNKNOWN')
    try:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='white', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='white', anchor="mm")"""

# This is the new code block with the requested changes.
new_code_block = """    # Guest Name (bigger font)
    name_y = info_y
    name_height = 120  # Increased height for bigger font
    if len(guest_name) > 20:
        words = guest_name.split(' ')
        if len(words) > 1:
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])
            try:
                draw.text((info_x + info_width//2, name_y + 40), line1, fill=navy_blue, anchor="mm", font_size=55)
                draw.text((info_x + info_width//2, name_y + 90), line2, fill=navy_blue, anchor="mm", font_size=55)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + 40), line1, fill=navy_blue, anchor="mm")
                draw.text((info_x + info_width//2, name_y + 90), line2, fill=navy_blue, anchor="mm")
        else:
            try:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=55)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")
    else:
        try:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=60)
        except TypeError:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")

    # Guest Role (black color)
    role_y = name_y + name_height
    role_height = 60
    try:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='black', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='black', anchor="mm")

    # Guest ID (black color)
    id_y = role_y + role_height + 10
    id_height = 60
    guest_id = guest.get('ID', 'UNKNOWN')
    try:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='black', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='black', anchor="mm")

    # Guest Phone (newly added, black color)
    phone_y = id_y + id_height + 10
    phone_height = 60
    guest_phone = guest.get('Phone', 'N/A')
    try:
        draw.text((info_x + info_width//2, phone_y + phone_height//2), f"Phone: {guest_phone}", fill='black', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, phone_y + phone_height//2), f"Phone: {guest_phone}", fill='black', anchor="mm")"""

# --- Patching Logic ---
try:
    # Read the original file content with UTF-8 encoding
    with open(file_to_patch, 'r', encoding='utf-8') as file:
        original_content = file.read()

    # Check if the patch has already been applied
    if new_code_block in original_content:
        print(f"Patch seems to be already applied to {file_to_patch}. No changes made.")
    # Check if the original code exists to be patched
    elif original_code_block in original_content:
        # Replace the old code with the new code
        updated_content = original_content.replace(original_code_block, new_code_block)

        # Write the updated content back to the file with UTF-8 encoding
        with open(file_to_patch, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        print(f"Successfully applied patch to {file_to_patch}")
    else:
        print(f"Error: Could not find the code block to patch in {file_to_patch}.")
        print("The file content may have changed. Please apply the changes manually.")

except FileNotFoundError:
    print(f"Error: The file '{file_to_patch}' was not found.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")