function logout() {
  document.cookie = "strinks_user_id= ; expires = Thu, 01 Jan 1970 00:00:00 GMT";
  location.reload();
}
