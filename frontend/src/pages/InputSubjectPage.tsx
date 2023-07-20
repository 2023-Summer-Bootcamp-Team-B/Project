import { observer } from "mobx-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import 햇님 from "../assets/images/햇님.svg";
import Background from "../components/Background";
import WebsocketStore from "../stores/WebsocketStore";

const InputSubjectPage = observer(() => {
  const { round, total } = WebsocketStore;
  const navigate = useNavigate();
  const [input, setInput] = useState("");

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.currentTarget.value);
  };
  const handleSubmit = () => {
    console.log("InputSubjectPage에서 편집버튼 누름", input);
  };

  if (round === 2) {
    navigate("/input");
  }

  return (
    <Background
      title="주제를 입력하세요!"
      input={input}
      round={round}
      total={total}
      handleInput={handleInput}
      handleSubmit={handleSubmit}
    >
      <img
        src={햇님}
        alt="sun"
        className="w-[500px] h-[400px] mx-auto relative z-40 ml-20 pb-10 p-4"
      />
    </Background>
  );
});

export default InputSubjectPage;
