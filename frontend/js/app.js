const SUPABASE_URL = "https://pptjaflkltwavyktzphw.supabase.co";

const SUPABASE_KEY = "sb_publishable_lUq2yPmkTijaqyYDifTYFA_Es-Xi7Nb";

const supabaseClient = supabase.createClient(
  SUPABASE_URL,
  SUPABASE_KEY
);

async function loadCourses() {

  const { data, error } = await supabaseClient
    .from("courses")
    .select("*");

  console.log(data);

}

loadCourses();
