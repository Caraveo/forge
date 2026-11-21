using System.Text.RegularExpressions;

internal static class Intent {
    // Returns the buildable idea in a chat message, or null for small talk and questions.
    // Chat only offers Image / 3D buttons (and "make it" only reuses a subject) when this finds one.
    public static string Subject(string text) {
        string s = Regex.Replace((text ?? "").Trim(), @"\s+", " ");
        if (s.Length == 0 || s.EndsWith("?")) return null;
        if (Regex.IsMatch(s, @"^(how|what|why|when|where|who|which|can|could|would|should|is|are|do|does|did|will|tell me|explain|help)\b", RegexOptions.IgnoreCase)) return null;
        string small = @"^(hi|hii+|hello|hey|heya|yo|sup|hiya|howdy|greetings|thanks|thank you|thx|ty|ok|okay|k|cool|nice|great|awesome|lol|haha|bye|goodbye|good (morning|afternoon|evening|night)|gm|gn|yes|yeah|yep|no|nope|sure|please|sorry|wow|test|testing)\b";
        if (Regex.IsMatch(s, small + @"[\s,.!:;)(-]*(there|forge|again|all|guys|buddy|friend|so much|a lot|everyone)?[\s,.!:;)(-]*$", RegexOptions.IgnoreCase)) return null;
        s = Regex.Replace(s, @"^(i('m| am) (thinking|dreaming) (about|of)|i('d| would) like|i want|maybe|how about|what about|let's (make|do|try)|imagine)\s+", "", RegexOptions.IgnoreCase);
        s = s.Trim(' ', '.', '!', ',');
        // An idea needs at least one real word beyond filler.
        var stop = new[] { "a", "an", "the", "of", "and", "with", "in", "on", "for", "to", "my", "me", "it", "this", "that", "some", "very", "really", "just" };
        foreach (Match m in Regex.Matches(s, @"[A-Za-z]{3,}"))
            if (System.Array.IndexOf(stop, m.Value.ToLowerInvariant()) < 0) return s.Length > 160 ? s.Substring(0, 160) : s;
        return null;
    }
    // Mirrors infer_quality in desktop/runner.py, which applies the preset.
    public static string Quality(string text) {
        if (Regex.IsMatch(text, @"\b(?:draft|low[- ]quality|low[- ]?res)\b", RegexOptions.IgnoreCase)) return "draft";
        if (Regex.IsMatch(text, @"\b(?:super|superior|supreme|high[- ]quality|quality|hq|prime|premium|ultra|best|detailed|hi[- ]?res|high[- ]res(?:olution)?|masterpiece)\b", RegexOptions.IgnoreCase)) return "high";
        return "standard";
    }
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
