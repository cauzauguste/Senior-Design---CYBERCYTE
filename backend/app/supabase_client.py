import os

try:
    from supabase import create_client, Client  # type: ignore
except ImportError:
    create_client = None
    Client = None


class SupabaseClient:
    def __init__(self):
        if create_client is None:
            raise RuntimeError(
                "Supabase library not installed. Install `supabase-py` or "
                "switch DB_BACKEND=postgres."
            )

        self.url: str = os.getenv("SUPABASE_URL")
        self.key: str = os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("❌ Supabase credentials not found in environment variables.")

        self.client: Client = create_client(self.url, self.key)
        print("✅ Supabase client initialized successfully")

    # rest of your methods unchanged...
    def insert_threat(self, threat_data: dict):
        """
        Insert a detected threat into the 'threat_logs' table.
        """
        try:
            response = self.client.table("threat_logs").insert(threat_data).execute()
            print(f"🚨 Threat logged: {threat_data}")
            return response
        except Exception as e:
            print(f"❌ Failed to insert threat: {e}")
            return None

    def get_threats(self):
        """
        Retrieve all logged threats from the 'threat_logs' table.
        """
        try:
            response = self.client.table("threat_logs").select("*").execute()
            return response.data
        except Exception as e:
            print(f"❌ Failed to fetch threats: {e}")
            return []
