using System.Text.RegularExpressions;

internal static class Intent {
    public static string Mode(string text) {
        string request = text.Trim();
        if (Regex.IsMatch(request, @"^(hi|hello|hey|thanks|thank you|how|what|why|when|where)\b", RegexOptions.IgnoreCase)) return "chat";
        request = Regex.Replace(request, @"^(?:(?:please|can you|could you|would you)\s+)+", "", RegexOptions.IgnoreCase);
        if (Regex.IsMatch(request, @"^(make sense|make sure|build up|imagine if)\b", RegexOptions.IgnoreCase)) return "chat";
        if (Regex.IsMatch(request, @"^(don't|do not|never)\b", RegexOptions.IgnoreCase)) return "chat";
        if (Regex.IsMatch(request, @"^remove\s+(?:the\s+)?background\b", RegexOptions.IgnoreCase)) return "background";
        if (Regex.IsMatch(request, @"^upscale\b", RegexOptions.IgnoreCase)) return "upscale";
        if (Regex.IsMatch(request, @"^rig\b", RegexOptions.IgnoreCase)) return "rig";
        if (Regex.IsMatch(request, @"^(generate|create|imagine|image)\b", RegexOptions.IgnoreCase)) return "image";
        if (Regex.IsMatch(request, @"^(forge|build|make|mold)\b", RegexOptions.IgnoreCase)) return "model";
        return "chat";
    }
}
