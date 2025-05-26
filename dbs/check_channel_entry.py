import sqlitedict

allowed_channels = sqlitedict.SqliteDict("allowed_channels.sqlite", autocommit=True)

# List all keys
print("All keys:")
for k in allowed_channels.keys():
    print(k)

# Print key-value pairs
print("\nAll key-value pairs:")
for k, v in allowed_channels.items():
    print(f"{k}: {v}")

allowed_channels.close()
